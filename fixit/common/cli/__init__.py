# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Shared utilities for tools that need to run lint rules from the command line.
"""

import itertools
import multiprocessing
import os
import subprocess
from enum import Enum  # noqa: IG29: The linter shouldn't depend on distillery's libs
from pathlib import Path
from typing import Callable, Collection, Iterable, Iterator, Tuple, TypeVar, Union

from fixit.common.config import REPO_ROOT


_MapPathsOperationConfigT = TypeVar("_MapPathsOperationConfigT")
_MapPathsOperationResultT = TypeVar("_MapPathsOperationResultT")
_MapPathsOperationT = Callable[
    [Path, _MapPathsOperationConfigT], _MapPathsOperationResultT
]
_MapPathsWorkerArgsT = Tuple[_MapPathsOperationT, Path, _MapPathsOperationConfigT]


class LintWorkers(Enum):
    # Spawn (up to) one worker process per CPU core
    CPU_COUNT = "cpu_count"
    # Disable the process pool, and compute results in the current thread and process.
    #
    # This can be useful for debugging, where the process pool may break tracebacks,
    # debuggers, or profilers.
    USE_CURRENT_THREAD = "use_current_thread"


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
def _map_paths_worker(args: _MapPathsWorkerArgsT) -> _MapPathsOperationResultT:
    operation, path, config = args
    return operation(path, config)


def map_paths(
    operation: _MapPathsOperationT,
    paths: Iterable[Path],
    config: _MapPathsOperationConfigT,
    *,
    workers: Union[int, LintWorkers] = LintWorkers.CPU_COUNT,
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

    Derived from `static_analysis.codemod.common.cli`, but it operates on a path instead
    of a code string.

    CAUTION: This function has a large overhead (multiple forks, tons of disk IO).
    """

    # TODO: We should use pyfmtd once it's available in IGSRV. If we can call it's IPC
    # directly (without a fork) that would be even better.

    black = REPO_ROOT / "bin" / "isort-black"
    args = (str(black), str(path), "--no-diff")
    formatted = subprocess.check_output(args, env={})
    with open(path, "wb") as f:
        f.write(formatted)
