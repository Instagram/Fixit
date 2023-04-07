# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import traceback
from functools import partial
from pathlib import Path
from typing import Generator, Iterable, List, Optional

import click
import trailrunner
from moreorless.click import echo_color_precomputed_diff

from .config import collect_rules, generate_config
from .engine import LintRunner
from .ftypes import Config, FileContent, LintViolation, Result

LOG = logging.getLogger(__name__)


def print_result(result: Result, show_diff: bool = False) -> None:
    """
    Print linting results in a simple format designed for human eyes.

    Setting ``show_diff=True`` will output autofixes or suggested changes in unified
    diff format, using ANSI colors when possible.
    """
    path = result.path
    try:
        path = path.relative_to(Path.cwd())
    except ValueError:
        pass

    if result.violation:
        rule_name = result.violation.rule_name
        start_line = result.violation.range.start.line
        start_col = result.violation.range.start.column
        message = result.violation.message
        if result.violation.autofixable:
            message += " (has autofix)"
        click.secho(
            f"{path}@{start_line}:{start_col} {rule_name}: {message}",
            fg="white" if result.violation.autofixable else "yellow",
        )
        if show_diff and result.violation.diff:
            echo_color_precomputed_diff(result.violation.diff)

    elif result.error:
        # An exception occurred while processing a file
        error, tb = result.error
        click.secho(f"{path}: EXCEPTION: {error}", fg="red")
        click.echo(tb.strip())


def fixit_bytes(
    path: Path,
    content: FileContent,
    *,
    config: Config,
    autofix: bool = False,
) -> Generator[Result, bool, Optional[FileContent]]:
    """
    Lint raw bytes content representing a single path, using the given configuration.

    Yields :class:`Result` objects for each lint error or exception found.
    Returns the final :class:`FileContent` including any fixes applied.

    Use :func:`capture` to more easily capture return value after iterating through
    violations. Use ``generator.send(...)`` with a boolean value to apply individual
    fixes for each violation.

    If ``autofix`` is ``True``, all violations with replacements will be applied
    automatically, even if ``False`` is sent back to the generator.
    """
    try:
        rules = collect_rules(config.enable, config.disable)
        runner = LintRunner(path, content)
        pending_fixes: List[LintViolation] = []

        for violation in runner.collect_violations(rules, config):
            fix = yield Result(path, violation)
            if fix or autofix:
                pending_fixes.append(violation)

        if pending_fixes:
            updated = runner.apply_replacements(pending_fixes)
            return updated

    except Exception as error:
        # TODO: this is not the right place to catch errors
        LOG.debug("Exception while linting", exc_info=error)
        yield Result(path, violation=None, error=(error, traceback.format_exc()))

    return None


def fixit_file(
    path: Path,
    *,
    autofix: bool = False,
) -> Generator[Result, None, None]:
    """
    Lint a single file on disk, detecting and generating appropriate configuration.

    Generates a merged :ref:`configuration` based on all applicable config files.
    Reads file from disk as raw bytes, and uses :func:`fixit_bytes` to lint and apply
    any fixes to the content. Writes content back to disk if changes are detected.

    Yields :class:`Result` objects for each lint error or exception found.
    See :func:`fixit_bytes` for semantics.
    """
    path = path.resolve()

    try:
        content: FileContent = path.read_bytes()
        config = generate_config(path)

        updated = yield from fixit_bytes(path, content, config=config, autofix=autofix)
        if updated and updated != content:
            LOG.info(f"{path}: writing changes to file")
            path.write_bytes(updated)

    except Exception as error:
        LOG.debug("Exception while fixit_file", exc_info=error)
        yield Result(path, violation=None, error=(error, traceback.format_exc()))


def _fixit_file_wrapper(path: Path, *, autofix: bool = False) -> List[Result]:
    """
    Wrapper because generators can't be pickled or used directly via multiprocessing
    TODO: replace this with some sort of queue or whatever
    """
    return list(fixit_file(path, autofix=autofix))


def fixit_paths(
    paths: Iterable[Path],
    *,
    autofix: bool = False,
) -> Generator[Result, None, None]:
    """
    Lint multiple files or directories, recursively expanding each path.

    Walks all paths given, obeying any ``.gitignore`` exclusions, finding Python source
    files. Lints each file found using :func:`fixit_file`, using a process pool when
    more than one file is being linted.

    Yields :class:`Result` objects for each lint error or exception found.
    See :func:`fixit_bytes` for semantics.

    .. note::

        Currently does not support applying individual fixes, due to limitations in the
        multiprocessing method in use. Setting ``autofix=True`` will still apply all
        fixes automatically during linting.
    """
    if not paths:
        return

    expanded_paths: List[Path] = []
    for path in paths:
        expanded_paths.extend(trailrunner.walk(path))

    if len(expanded_paths) == 1:
        yield from fixit_file(expanded_paths[0], autofix=autofix)
    else:
        fn = partial(_fixit_file_wrapper, autofix=autofix)
        for _, results in trailrunner.run_iter(expanded_paths, fn):
            yield from results
