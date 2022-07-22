# Copyright (c) Meta Platforms, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path
from typing import Generator, Iterable, List

import trailrunner

from .config import generate_config
from .types import Config, FileContent, Result


def fixit_bytes(
    path: Path,
    content: FileContent,
    *,
    config: Config,
) -> Generator[Result, None, None]:
    """
    Lint raw bytes content representing a single path, using the given configuration.
    """
    if False:  # force a generator until this gets implemented
        yield Result()


def fixit_file(
    path: Path,
) -> Generator[Result, None, None]:
    """
    Lint a single file on disk.
    """
    path = path.resolve()

    try:
        content: FileContent = path.read_bytes()
        config = generate_config(path)

        yield from fixit_bytes(path, content, config=config)

    except Exception as error:
        yield Result(path, error=error)


def fixit_paths(
    paths: Iterable[Path],
) -> Generator[Result, None, None]:
    """
    Lint multiple files or directories, recursively expanding each path.
    """
    if not paths:
        return

    expanded_paths: List[Path] = []
    for path in paths:
        expanded_paths.extend(trailrunner.walk(path))

    for path in expanded_paths:
        yield from fixit_file(path)
