# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import sys
from pathlib import Path
from typing import Iterable, Optional, Set

import click

from fixit import __version__

from .api import fixit_paths, print_result
from .config import collect_rules, generate_config
from .ftypes import Options
from .util import capture


def splash(
    visited: Set[Path], dirty: Set[Path], autofixes: int = 0, fixed: int = 0
) -> None:
    def f(v: int) -> str:
        return "file" if v == 1 else "files"

    if dirty:
        reports = [
            click.style(f"{len(visited)} {f(len(visited))} checked"),
            click.style(
                f"{len(dirty)} {f(len(dirty))} with errors", fg="yellow", bold=True
            ),
        ]
        if autofixes:
            word = "fix" if autofixes == 1 else "fixes"
            reports += [click.style(f"{autofixes} auto-{word} available", bold=True)]
        if fixed:
            word = "fix" if fixed == 1 else "fixes"
            reports += [click.style(f"{fixed} {word} applied", bold=True)]

        message = ", ".join(reports)
        click.secho(f"🛠️  {message} 🛠️", err=True)
    else:
        click.secho(f"🧼 {len(visited)} {f(len(visited))} clean 🧼", err=True)


@click.group()
@click.pass_context
@click.version_option(__version__, "--version", "-V", prog_name="fixit")
@click.option(
    "--debug/--quiet", is_flag=True, default=None, help="Increase decrease verbosity"
)
@click.option(
    "--config-file",
    "-c",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
    default=None,
    help="Override default config file search behavior",
)
def main(
    ctx: click.Context,
    debug: Optional[bool],
    config_file: Optional[Path],
):
    level = logging.WARNING
    if debug is not None:
        level = logging.DEBUG if debug else logging.ERROR
    logging.basicConfig(level=level, stream=sys.stderr)

    ctx.obj = Options(
        debug=debug,
        config_file=config_file,
    )


@main.command()
@click.pass_context
@click.option("--diff", "-d", is_flag=True, help="Show diff of suggested changes")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def lint(
    ctx: click.Context,
    diff: bool,
    paths: Iterable[Path],
):
    """
    lint one or more paths and return suggestions
    """
    exit_code = 0
    visited: Set[Path] = set()
    dirty: Set[Path] = set()
    autofixes = 0
    for result in fixit_paths(paths):
        visited.add(result.path)

        if print_result(result, show_diff=diff):
            dirty.add(result.path)
            if result.violation:
                exit_code |= 1
                if result.violation.autofixable:
                    autofixes += 1
            if result.error:
                exit_code |= 2

    splash(visited, dirty, autofixes)
    ctx.exit(exit_code)


@main.command()
@click.pass_context
@click.option(
    "--interactive/--automatic",
    "-i/-a",
    is_flag=True,
    default=True,
    help="how to apply fixes; interactive by default",
)
@click.option("--diff", "-d", is_flag=True, help="show diff even with --automatic")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def fix(
    ctx: click.Context,
    interactive: bool,
    diff: bool,
    paths: Iterable[Path],
):
    """
    lint and autofix one or more files and return results
    """
    autofix = not interactive
    exit_code = 0

    visited: Set[Path] = set()
    dirty: Set[Path] = set()
    autofixes = 0
    fixed = 0

    # TODO: make this parallel
    generator = capture(fixit_paths(paths, autofix=autofix, parallel=False))
    for result in generator:
        visited.add(result.path)
        if print_result(result, show_diff=interactive or diff):
            dirty.add(result.path)
            if autofix and result.violation and result.violation.autofixable:
                autofixes += 1
                fixed += 1
        if interactive and result.violation and result.violation.autofixable:
            autofixes += 1
            answer = click.prompt(
                "Apply autofix?", default="y", type=click.Choice("ynq", False)
            )
            if answer == "y":
                generator.respond(True)
                fixed += 1
            elif answer == "q":
                break

    splash(visited, dirty, autofixes, fixed)
    ctx.exit(exit_code)


@main.command()
@click.pass_context
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def debug(ctx: click.Context, paths: Iterable[Path]):
    """
    print debug info for each path
    """
    try:
        from rich import print as pprint
    except ImportError:
        from pprint import pprint  # type: ignore

    for path in paths:
        path = path.resolve()
        config = generate_config(path)
        rules = collect_rules(config.enable, config.disable)

        pprint(">>> ", path)
        pprint(config)
        pprint(rules)
