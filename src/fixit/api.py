# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import sys
import traceback
from functools import partial
from pathlib import Path
from typing import Generator, Iterable, List, Optional

import click
import trailrunner
from moreorless.click import echo_color_precomputed_diff

from .config import collect_rules, generate_config
from .engine import LintRunner
from .format import format_module
from .ftypes import (
    Config,
    FileContent,
    LintViolation,
    LoggerHook,
    Options,
    OutputFormat,
    Result,
    STDIN,
)

LOG = logging.getLogger(__name__)


def print_result(
    result: Result,
    *,
    show_diff: bool = False,
    stderr: bool = False,
    output_format: OutputFormat = OutputFormat.fixit,
    output_template: str = "",
) -> int:
    """
    Print linting results in a simple format designed for human eyes.

    Setting ``show_diff=True`` will output autofixes or suggested changes in unified
    diff format, using ANSI colors when possible.

    Returns ``True`` if the result is "dirty" - either a lint error or exception.
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

        if output_format == OutputFormat.fixit:
            line = f"{path}@{start_line}:{start_col} {rule_name}: {message}"
        elif output_format == OutputFormat.vscode:
            line = f"{path}:{start_line}:{start_col} {rule_name}: {message}"
        elif output_format == OutputFormat.custom:
            line = output_template.format(
                message=message,
                path=path,
                result=result,
                rule_name=rule_name,
                start_col=start_col,
                start_line=start_line,
            )
        else:
            raise NotImplementedError(f"output-format = {output_format!r}")
        click.secho(line, fg="yellow", err=stderr)

        if show_diff and result.violation.diff:
            echo_color_precomputed_diff(result.violation.diff)
        return True

    elif result.error:
        # An exception occurred while processing a file
        error, tb = result.error
        click.secho(f"{path}: EXCEPTION: {error}", fg="red", err=stderr)
        click.echo(tb.strip(), err=stderr)
        return True

    else:
        LOG.debug("%s: clean", path)
        return False


def fixit_bytes(
    path: Path,
    content: FileContent,
    *,
    config: Config,
    autofix: bool = False,
    logger_hook: Optional[LoggerHook] = None,
) -> Generator[Result, bool, Optional[FileContent]]:
    """
    Lint raw bytes content representing a single path, using the given configuration.

    Yields :class:`Result` objects for each lint error or exception found, or a single
    empty result if the file is clean. A file is considered clean if no lint errors or
    no rules are enabled for the given path.
    Returns the final :class:`FileContent` including any fixes applied.

    Use :func:`capture` to more easily capture return value after iterating through
    violations. Use ``generator.send(...)`` with a boolean value to apply individual
    fixes for each violation.

    If ``autofix`` is ``True``, all violations with replacements will be applied
    automatically, even if ``False`` is sent back to the generator.

    """
    try:
        rules = collect_rules(config)

        if not rules:
            yield Result(path, violation=None)
            return None

        runner = LintRunner(path, content)
        pending_fixes: List[LintViolation] = []

        clean = True
        for violation in runner.collect_violations(rules, config, logger_hook):
            clean = False
            fix = yield Result(path, violation)
            if fix or autofix:
                pending_fixes.append(violation)

        if clean:
            yield Result(path, violation=None)

        if pending_fixes:
            updated = runner.apply_replacements(pending_fixes)
            return format_module(updated, path, config)

    except Exception as error:
        # TODO: this is not the right place to catch errors
        LOG.debug("Exception while linting", exc_info=error)
        yield Result(path, violation=None, error=(error, traceback.format_exc()))

    return None


def fixit_stdin(
    path: Path,
    *,
    autofix: bool = False,
    options: Optional[Options] = None,
    logger_hook: Optional[LoggerHook] = None,
) -> Generator[Result, bool, None]:
    """
    Wrapper around :func:`fixit_bytes` for formatting content from STDIN.

    The resulting fixed content will be printed to STDOUT.

    Requires passing a path that represents the filesystem location matching the
    contents to be linted. This will be used to resolve the ``fixit.toml`` config
    file(s).
    """
    path = path.resolve()

    try:
        content: FileContent = sys.stdin.buffer.read()
        config = generate_config(path, options=options)

        updated = yield from fixit_bytes(
            path, content, config=config, autofix=autofix, logger_hook=logger_hook
        )
        if autofix:
            sys.stdout.buffer.write(updated or content)

    except Exception as error:
        LOG.debug("Exception while fixit_stdin", exc_info=error)
        yield Result(path, violation=None, error=(error, traceback.format_exc()))


def fixit_file(
    path: Path,
    *,
    autofix: bool = False,
    options: Optional[Options] = None,
    logger_hook: Optional[LoggerHook] = None,
) -> Generator[Result, bool, None]:
    """
    Lint a single file on disk, detecting and generating appropriate configuration.

    Generates a merged :ref:`configuration` based on all applicable config files.
    Reads file from disk as raw bytes, and uses :func:`fixit_bytes` to lint and apply
    any fixes to the content. Writes content back to disk if changes are detected.

    Yields :class:`Result` objects for each lint error or exception found, or a single
    empty result if the file is clean.
    See :func:`fixit_bytes` for semantics.
    """
    path = path.resolve()

    try:
        content: FileContent = path.read_bytes()
        config = generate_config(path, options=options)

        updated = yield from fixit_bytes(
            path, content, config=config, autofix=autofix, logger_hook=logger_hook
        )
        if updated and updated != content:
            LOG.info(f"{path}: writing changes to file")
            path.write_bytes(updated)

    except Exception as error:
        LOG.debug("Exception while fixit_file", exc_info=error)
        yield Result(path, violation=None, error=(error, traceback.format_exc()))


def _fixit_file_wrapper(
    path: Path,
    *,
    autofix: bool = False,
    options: Optional[Options] = None,
    logger_hook: Optional[LoggerHook] = None,
) -> List[Result]:
    """
    Wrapper because generators can't be pickled or used directly via multiprocessing
    TODO: replace this with some sort of queue or whatever
    """
    return list(
        fixit_file(path, autofix=autofix, options=options, logger_hook=logger_hook)
    )


def fixit_paths(
    paths: Iterable[Path],
    *,
    autofix: bool = False,
    options: Optional[Options] = None,
    parallel: bool = True,
    logger_hook: Optional[LoggerHook] = None,
) -> Generator[Result, bool, None]:
    """
    Lint multiple files or directories, recursively expanding each path.

    Walks all paths given, obeying any ``.gitignore`` exclusions, finding Python source
    files. Lints each file found using :func:`fixit_file`, using a process pool when
    more than one file is being linted.

    Yields :class:`Result` objects for each path, lint error, or exception found.
    See :func:`fixit_bytes` for semantics.

    If the first given path is STDIN (``Path("-")``), then content will be linted
    from STDIN using :func:`fixit_stdin`. The fixed content will be written to STDOUT.
    A second path argument may be given, which represents the original content's true
    path name, and will be used:
    - to resolve the ``fixit.toml`` configuration file(s)
    - when printing status messages, diffs, or errors.
    If no second path argument is given, it will default to "stdin" in the current
    working directory.
    Any further path names will result in a runtime error.

    .. note::

        Currently does not support applying individual fixes when ``parallel=True``,
        due to limitations in the multiprocessing method in use.
        Setting ``parallel=False`` will enable interactive fixes.
        Setting ``autofix=True`` will always apply fixes automatically during linting.
    """
    if not paths:
        return

    expanded_paths: List[Path] = []
    is_stdin = False
    stdin_path = Path("stdin")
    for i, path in enumerate(paths):
        if path == STDIN:
            if i == 0:
                is_stdin = True
            else:
                LOG.warning("Cannot mix stdin ('-') with normal paths, ignoring")
        elif is_stdin:
            if i == 1:
                stdin_path = path
            else:
                raise ValueError("too many stdin paths")
        else:
            expanded_paths.extend(trailrunner.walk(path))

    if is_stdin:
        yield from fixit_stdin(
            stdin_path, autofix=autofix, options=options, logger_hook=logger_hook
        )
    elif len(expanded_paths) == 1 or not parallel:
        for path in expanded_paths:
            yield from fixit_file(
                path, autofix=autofix, options=options, logger_hook=logger_hook
            )
    else:
        fn = partial(
            _fixit_file_wrapper,
            autofix=autofix,
            options=options,
            logger_hook=logger_hook,
        )
        for _, results in trailrunner.run_iter(expanded_paths, fn):
            yield from results
