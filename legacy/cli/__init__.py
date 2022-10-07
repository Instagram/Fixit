# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Shared utilities for tools that need to run lint rules from the command line.
"""
import argparse
import itertools
import json
import multiprocessing
import os
import traceback
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import (
    Callable,
    Collection,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TYPE_CHECKING,
    TypeVar,
    Union,
)

import libcst as cst
from libcst.metadata import MetadataWrapper

from fixit.cli.args import get_multiprocessing_parser, LintWorkers
from fixit.common.base import LintConfig
from fixit.common.config import get_lint_config
from fixit.common.full_repo_metadata import FullRepoMetadataConfig, get_repo_caches
from fixit.common.report import LintFailureReportBase, LintSuccessReportBase
from fixit.common.utils import LintRuleCollectionT
from fixit.rule_lint_engine import lint_file


if TYPE_CHECKING:
    from libcst.metadata.base_provider import ProviderT

_MapPathsOperationConfigT = TypeVar("_MapPathsOperationConfigT")
_MapPathsOperationResultT = TypeVar("_MapPathsOperationResultT")
_MapPathsOperationT = Callable[
    [Path, _MapPathsOperationConfigT, Optional[Mapping["ProviderT", object]]],
    _MapPathsOperationResultT,
]
_MapPathsWorkerArgsT = Tuple[
    _MapPathsOperationT,
    str,
    _MapPathsOperationConfigT,
    Optional[Mapping["ProviderT", object]],
]


def find_files(paths: Iterable[Union[str, Path]]) -> Iterator[str]:
    """
    Given an iterable of paths, yields any files and walks over any directories.
    """
    for path in paths:
        if os.path.isfile(path):
            yield str(path)
        else:
            for root, _dirs, files in os.walk(path):
                for f in files:
                    if f.endswith(".py") and not os.path.islink(f):
                        yield os.path.join(root, f)


# Multiprocessing can only pass one argument. Wrap `operation` to provide this.
# pyre-fixme[34]: `Variable[_MapPathsOperationResultT]` isn't present in the
#  function's parameters.
def _map_paths_worker(args: _MapPathsWorkerArgsT) -> _MapPathsOperationResultT:
    operation, path, config, metadata_caches = args
    return operation(Path(path), config, metadata_caches)


def map_paths(
    operation: _MapPathsOperationT,
    paths: Iterable[str],
    config: _MapPathsOperationConfigT,
    *,
    workers: Union[int, LintWorkers] = LintWorkers.CPU_COUNT,
    metadata_caches: Optional[Mapping[str, Mapping["ProviderT", object]]] = None,
    # pyre-fixme[34]: `Variable[_MapPathsOperationResultT]` isn't present in the
    #  function's parameters.
) -> Iterator[_MapPathsOperationResultT]:
    """
    Applies the given `operation` to each file path in `paths`.

    This uses a process pool by default, but if `workers` is
    `LintWorkers.USE_CURRENT_THREAD`, the process pool is disabled and rules are
    processed on the current thread. This is useful for profiling and debugging.

    `operation` must be a top-level function (not a method or inner function), since it
    needs to be imported by pickle and used across process boundaries.
    NOTE: this function does not verify the signature of `operation`. If `metadata_caches`
    is passed in, it is up to the caller to make sure that `operation` is equipped to handle
    a `MetadataWrapper` argument.

    `paths` should only contain file paths (not directories). Use `find_files` if you
    have directory paths and need to expand them.

    `metadata_caches` is an optional argument for those callers expecting to use type metadata
    for linting. If passed, it should be a mapping of Path to a LibCST MetadataWrapper to be used
    for the linting of the corresponding file.

    Results are yielded as soon as they're available, so they may appear out-of-order.
    """
    if workers is LintWorkers.CPU_COUNT:
        workers = multiprocessing.cpu_count()

    if metadata_caches is not None:
        tasks: Collection[_MapPathsWorkerArgsT] = tuple(
            zip(
                itertools.repeat(operation),
                metadata_caches.keys(),
                itertools.repeat(config),
                metadata_caches.values(),
            )
        )
    else:
        tasks: Collection[_MapPathsWorkerArgsT] = tuple(
            zip(
                itertools.repeat(operation),
                paths,
                itertools.repeat(config),
                itertools.repeat(None),
            )
        )
    if not tasks:
        # this would result in 0 workers, which will cause multiprocessing.Pool to die
        return

    if workers is LintWorkers.USE_CURRENT_THREAD:
        for t in tasks:
            yield _map_paths_worker(t)
    else:
        assert not isinstance(workers, LintWorkers), "Unreachable"
        # Don't spawn more processes than there are tasks. Multiprocessing is eager and
        # will spawn workers immediately even if there's no work for them to do.
        with multiprocessing.Pool(min(workers, len(tasks))) as pool:
            for result in pool.imap_unordered(_map_paths_worker, tasks):
                yield result


@dataclass(frozen=True)
class LintOpts:
    rules: LintRuleCollectionT
    success_report: Type[LintSuccessReportBase]
    failure_report: Type[LintFailureReportBase]
    config: LintConfig = get_lint_config()
    full_repo_metadata_config: Optional[FullRepoMetadataConfig] = None
    extra: Dict[str, object] = field(default_factory=dict)


def get_file_lint_result_json(
    path: Path,
    opts: LintOpts,
    metadata_cache: Optional[Mapping["ProviderT", object]] = None,
) -> Sequence[str]:
    try:
        with open(path, "rb") as f:
            source = f.read()
        cst_wrapper = None
        if metadata_cache is not None:
            cst_wrapper = MetadataWrapper(
                cst.parse_module(source),
                True,
                metadata_cache,
            )
        results = opts.success_report.create_reports(
            path,
            lint_file(
                path,
                source,
                rules=opts.rules,
                config=opts.config,
                cst_wrapper=cst_wrapper,
                find_unused_suppressions=True,
            ),
            **opts.extra,
        )
    except Exception:
        tb_str = traceback.format_exc()
        results = opts.failure_report.create_reports(path, tb_str, **opts.extra)
    return [json.dumps(asdict(r)) for r in results]


@dataclass(frozen=True)
class IPCResult:
    paths: List[str]


def run_ipc(
    opts: LintOpts,
    paths: List[str],
    prefix: Optional[str] = None,
    workers: LintWorkers = LintWorkers.CPU_COUNT,
) -> IPCResult:
    """
    Given a LintOpts config with lint rules and lint success/failure report formatter,
    this IPC helper takes a path of source files (with an optional `prefix` that will be prepended).
    Results are formed as JSON and delimited by newlines.
    It uses a multiprocess pool and the results are streamed to stdout as soon
    as they're available.

    Returns an IPCResult object.
    """

    resolved_paths = (os.path.join(prefix, p) if prefix else p for p in paths)

    full_repo_metadata_config = opts.full_repo_metadata_config
    metadata_caches: Optional[Mapping[str, Mapping["ProviderT", object]]] = None
    if full_repo_metadata_config is not None:
        metadata_caches = get_repo_caches(resolved_paths, full_repo_metadata_config)

    results_iter: Iterator[Sequence[str]] = map_paths(
        get_file_lint_result_json,
        resolved_paths,
        opts,
        workers=workers,
        metadata_caches=metadata_caches,
    )
    for results in results_iter:
        # Use print outside of the executor to avoid multiple processes trying to write
        # to stdout in parallel, which could cause a corrupted output.
        for result in results:
            print(result)

    return IPCResult(list(resolved_paths))


def ipc_main(opts: LintOpts) -> IPCResult:
    """
    Like `run_ipc` instead this function expects arguments to be collected through
    argparse. This IPC helper takes paths of source files from either a path file
    (with @paths arg) or a list of paths as args.

    Returns an IPCResult object.
    """
    warnings.warn(
        """
        Calling ipc_main as a command line tool is being deprecated.
        Please use the module-level function `run_ipc` instead.""",
        DeprecationWarning,
    )

    parser = argparse.ArgumentParser(
        description="Runs Fixit lint rules and print results as console output.",
        fromfile_prefix_chars="@",
        parents=[get_multiprocessing_parser()],
    )
    parser.add_argument("paths", nargs="*", help="List of paths to run lint rules on.")
    parser.add_argument("--prefix", help="A prefix to be added to all paths.")
    args: argparse.Namespace = parser.parse_args()

    return run_ipc(
        opts=opts, paths=args.paths, prefix=args.prefix, workers=args.workers
    )
