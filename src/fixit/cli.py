# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import sys
import unittest
from pathlib import Path
from typing import Dict, Optional, Sequence, Set, Type

import click

from fixit import __version__

from .api import fixit_paths, print_result
from .config import collect_rules, generate_config, parse_rule
from .ftypes import Config, Options, QualifiedRule, Tags
from .rule import LintRule
from .testing import generate_lint_rule_test_cases
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
@click.option(
    "--tags",
    type=str,
    default="",
    help="Select or filter rules by tags",
)
@click.option(
    "--rules",
    type=str,
    default="",
    help="Override configured rules",
)
def main(
    ctx: click.Context,
    debug: Optional[bool],
    config_file: Optional[Path],
    tags: str,
    rules: str,
):
    level = logging.WARNING
    if debug is not None:
        level = logging.DEBUG if debug else logging.ERROR
    logging.basicConfig(level=level, stream=sys.stderr)

    ctx.obj = Options(
        debug=debug,
        config_file=config_file,
        tags=Tags.parse(tags),
        rules=sorted(
            {
                parse_rule(r, Path.cwd())
                for r in (rs.strip() for rs in rules.split(","))
                if r
            }
        ),
    )


@main.command()
@click.pass_context
@click.option("--diff", "-d", is_flag=True, help="Show diff of suggested changes")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def lint(
    ctx: click.Context,
    diff: bool,
    paths: Sequence[Path],
):
    """
    lint one or more paths and return suggestions
    """
    options: Options = ctx.obj

    if not paths:
        paths = [Path.cwd()]

    exit_code = 0
    visited: Set[Path] = set()
    dirty: Set[Path] = set()
    autofixes = 0
    for result in fixit_paths(paths, options=options):
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
    paths: Sequence[Path],
):
    """
    lint and autofix one or more files and return results
    """
    options: Options = ctx.obj

    if not paths:
        paths = [Path.cwd()]

    autofix = not interactive
    exit_code = 0

    visited: Set[Path] = set()
    dirty: Set[Path] = set()
    autofixes = 0
    fixed = 0

    # TODO: make this parallel
    generator = capture(
        fixit_paths(paths, autofix=autofix, options=options, parallel=False)
    )
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
@click.argument("rules", nargs=-1, required=True, type=str)
def test(ctx: click.Context, rules: Sequence[str]):
    """
    test lint rules and their VALID/INVALID cases
    """
    qual_rules = [parse_rule(rule, Path.cwd().resolve()) for rule in rules]
    lint_rules = collect_rules(
        Config(enable=qual_rules, disable=[], python_version=None)
    )
    test_cases = generate_lint_rule_test_cases(lint_rules)

    test_suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for test_case in test_cases:
        test_suite.addTest(loader.loadTestsFromTestCase(test_case))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    if not result.wasSuccessful():
        ctx.exit(1)


@main.command()
@click.pass_context
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def upgrade(ctx: click.Context, paths: Sequence[Path]):
    """
    upgrade lint rules and apply deprecation fixes

    roughly equivalent to `fixit --rules fixit.upgrade fix --automatic`
    """
    options: Options = ctx.obj
    options.rules = (QualifiedRule("fixit.upgrade"),)

    ctx.invoke(fix, paths=paths, interactive=False)


@main.command()
@click.pass_context
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
def debug(ctx: click.Context, paths: Sequence[Path]):
    """
    print materialized configuration for paths
    """
    options: Options = ctx.obj

    if not paths:
        paths = [Path.cwd()]

    try:
        from rich import print as pprint
    except ImportError:
        from pprint import pprint  # type: ignore

    pprint(options)

    for path in paths:
        path = path.resolve()
        config = generate_config(path, options=options)
        disabled: Dict[Type[LintRule], str] = {}
        enabled = collect_rules(config, debug_reasons=disabled)

        pprint(">>> ", path)
        pprint(config)
        pprint("enabled:", sorted(str(rule) for rule in enabled))
        pprint(
            "disabled:",
            sorted(f"{rule()} ({reason})" for rule, reason in disabled.items()),
        )
