# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import traceback
from pathlib import Path
from typing import Generator, Iterable, List

import trailrunner

from .config import collect_rules, generate_config
from .engine import collect_violations
from .types import Config, FileContent, LintViolation, Result

logger = logging.getLogger(__name__)


def _make_result(path: Path, violations: Iterable[LintViolation]) -> Iterable[Result]:
    try:
        for violation in violations:
            yield Result(path, violation)
    except Exception as error:
        # TODO: this is not the right place to catch errors
        logger.debug("Exception while linting", exc_info=error)
        yield Result(path, violation=None, error=(error, traceback.format_exc()))


def fixit_bytes(
    path: Path,
    content: FileContent,
    *,
    config: Config,
) -> Generator[Result, None, None]:
    """
    Lint raw bytes content representing a single path, using the given configuration.
    """
    rules = collect_rules(config.enable, config.disable)
    yield from _make_result(path, collect_violations(content, rules))


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
        logger.debug("Exception while fixit_file", exc_info=error)
        yield Result(path, violation=None, error=(error, traceback.format_exc()))


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
