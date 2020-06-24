# Copyright (c) Facebook, Inc. and its affiliates.
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
import subprocess
import sys
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import (
    Callable,
    Collection,
    Generator,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from libcst.metadata.wrapper import MetadataWrapper

from fixit.common.cli.args import LintWorkers, get_multiprocessing_parser
from fixit.common.config import REPO_ROOT
from fixit.common.report import LintFailureReportBase, LintSuccessReportBase
from fixit.rule_lint_engine import LintRuleCollectionT, lint_file


_MapPathsOperationConfigT = TypeVar("_MapPathsOperationConfigT")
_MapPathsOperationResultT = TypeVar("_MapPathsOperationResultT")
_MapPathsOperationT = Callable[
    [Path, _MapPathsOperationConfigT], _MapPathsOperationResultT
]
_MapPathsOperationWithMetadataT = Callable[
    [Path, _MapPathsOperationConfigT, Optional[MetadataWrapper]],
    _MapPathsOperationResultT,
]
_MapPathsWorkerArgsT = Tuple[
    Union[_MapPathsOperationT, _MapPathsOperationWithMetadataT],
    Path,
    _MapPathsOperationConfigT,
]
_MapPathsWorkerArgsWithMetadataT = Tuple[
    _MapPathsOperationWithMetadataT,
    Path,
    _MapPathsOperationConfigT,
    Optional[MetadataWrapper],
]


def find_files(paths: Iterable[Path]) -> Iterator[Path]:
    """
    Given an iterable of paths, yields any files and walks over any directories.
    """
    for path in paths:
        if path.is_file():
            yield path
        else:
            for root, _dirs, files in os.walk(path):
                for f in files:
                    if f.endswith(".py") and not os.path.islink(f):
                        yield Path(root) / f


# Multiprocessing can only pass one argument. Wrap `operation` to provide this.
def _map_paths_worker(
    args: Union[_MapPathsWorkerArgsT, _MapPathsWorkerArgsWithMetadataT]
) -> _MapPathsOperationResultT:
    operation, path, *op_args = args
    return operation(path, *op_args)


def map_paths(
    operation: Union[_MapPathsOperationT, _MapPathsOperationWithMetadataT],
    paths: Iterable[Path],
    config: _MapPathsOperationConfigT,
    *,
    workers: Union[int, LintWorkers] = LintWorkers.CPU_COUNT,
    metadata_wrappers: Optional[Mapping[Path, MetadataWrapper]] = None,
) -> Iterator[_MapPathsOperationResultT]:
    """
    Applies the given `operation` to each file path in `paths`.

    This uses a process pool by default, but if `workers` is
    `LintWorkers.USE_CURRENT_THREAD`, the process pool is disabled and rules are
    processed on the current thread. This is useful for profiling and debugging.

    `operation` must be a top-level function (not a method or inner function), since it
    needs to be imported by pickle and used across process boundaries.

    `paths` should only contain file paths (not directories). Use `find_files` if you
    have directory paths and need to expand them.

    Results are yielded as soon as they're available, so they may appear out-of-order.
    """

    if workers is LintWorkers.CPU_COUNT:
        workers = multiprocessing.cpu_count()

    if metadata_wrappers is not None:
        # pyre-ignore[9]: tasks is declared to have type `Collection[typing.Tuple[typing.Callable[[Path, Variable[_MapPathsOperationConfigT], Optional[MetadataWrapper]],
        # Variable[_MapPathsOperationResultT]], Path, Variable[_MapPathsOperationConfigT], Optional[MetadataWrapper]]]`
        # but is used as type `typing.Tuple[typing.Tuple[typing.Callable[[Path, Variable[_MapPathsOperationConfigT]],
        # Variable[_MapPathsOperationResultT]], Path, Variable[_MapPathsOperationConfigT], Optional[MetadataWrapper]], ...]`.
        tasks: Collection[_MapPathsWorkerArgsWithMetadataT] = tuple(
            zip(
                itertools.repeat(operation),
                paths,
                itertools.repeat(config),
                map(metadata_wrappers.get, paths),
            )
        )
    else:
        tasks: Collection[_MapPathsWorkerArgsT] = tuple(
            zip(itertools.repeat(operation), paths, itertools.repeat(config))
        )
    if not tasks:
        # this would result in 0 workers, which will cause multiprocessing.Pool to die
        return

    if workers is LintWorkers.USE_CURRENT_THREAD:
        for t in tasks:
            yield _map_paths_worker(t)
    else:
        # lint-ignore: IG01: Asserts are okay in lint
        assert not isinstance(workers, LintWorkers), "Unreachable"
        # Don't spawn more processes than there are tasks. Multiprocessing is eager and
        # will spawn workers immediately even if there's no work for them to do.
        with multiprocessing.Pool(min(workers, len(tasks))) as pool:
            # pyre: Pyre doesn't understand something about the typevars used in this
            # pyre-fixme[6]: function call. I was unable to debug it.
            for result in pool.imap_unordered(_map_paths_worker, tasks):
                yield result


def pyfmt(path: Union[str, Path]) -> None:
    """
    Given a path, run isort-black on the code and write the updated file back to disk.

    CAUTION: This function has a large overhead (multiple forks, tons of disk IO).
    """

    # TODO: We should use pyfmtd once it's available in IGSRV. If we can call it's IPC
    # directly (without a fork) that would be even better.

    black = REPO_ROOT / "bin" / "isort-black"
    args = (str(black), str(path), "--no-diff")
    formatted = subprocess.check_output(args, env={})
    with open(path, "wb") as f:
        f.write(formatted)


@dataclass(frozen=True)
class LintOpts:
    rules: LintRuleCollectionT
    success_report: Type[LintSuccessReportBase]
    failure_report: Type[LintFailureReportBase]


def get_file_lint_result_json(path: Path, opts: LintOpts) -> Sequence[str]:
    try:
        with open(path, "rb") as f:
            source = f.read()
        results = opts.success_report.create_reports(
            path, lint_file(path, source, rules=opts.rules)
        )
    except Exception:
        tb_str = traceback.format_exc()
        results = opts.failure_report.create_reports(path, tb_str)
    return [json.dumps(asdict(r)) for r in results]


def ipc_main(opts: LintOpts) -> None:
    """
    Given a LintOpts config with lint rules and lint success/failure report formatter,
    this IPC helper took paths of source file paths from either stdin (newline-delimited
    UTF-8 values), list of paths in a path file (with @paths arg) or a list of paths as
    args. Results are formed as JSON and delimited by
    newlines. It uses a multi process pool and the results are streamed to stdout as soon
    as they're available. For stdin paths, they are evaluated as soon as they're read from
    the pipe.
    """
    parser = argparse.ArgumentParser(
        description="Runs Fixit lint rules and print results as console output.",
        fromfile_prefix_chars="@",
        parents=[get_multiprocessing_parser()],
    )
    parser.add_argument("paths", nargs="*", help="List of paths to run lint rules on.")
    parser.add_argument("--prefix", help="A prefix to be added to all paths.")
    args: argparse.Namespace = parser.parse_args()
    if args.prefix:
        prefix_path = Path(args.prefix)

        def process_path(p: str) -> Path:
            return prefix_path / p

    else:

        def process_path(p: str) -> Path:
            return Path(p)

    if args.paths:
        paths: Generator[Path, None, None] = (process_path(p) for p in args.paths)
    else:
        paths: Generator[Path, None, None] = (
            process_path(p.rstrip("\r\n")) for p in sys.stdin
        )

    results_iter: Iterator[Sequence[str]] = map_paths(
        get_file_lint_result_json, paths, opts, workers=args.workers
    )
    for results in results_iter:
        # Use print outside of the executor to avoid multiple processes trying to write
        # to stdout in parallel, which could cause a corrupted output.
        for result in results:
            print(result)
