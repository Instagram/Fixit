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

from .api import fixit_paths, print_result, validate_config
from .config import collect_rules, generate_config, parse_rule
from .ftypes import Config, LSPOptions, Options, OutputFormat, QualifiedRule, Tags
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
@click.option(
    "--output-format",
    "-o",
    type=click.Choice([o.name for o in OutputFormat], case_sensitive=False),
    show_choices=True,
    default=None,
    help="Select output format type",
)
@click.option(
    "--output-template",
    type=str,
    default="",
    help="Python format template to use with output format 'custom'",
)
@click.option("--print-metrics", is_flag=True, help="Print metrics of this run")
def main(
    ctx: click.Context,
    debug: Optional[bool],
    config_file: Optional[Path],
    tags: str,
    rules: str,
    output_format: Optional[OutputFormat],
    output_template: str,
    print_metrics: bool,
) -> None:
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
        output_format=output_format,
        output_template=output_template,
        print_metrics=print_metrics,
    )


@main.command()
@click.pass_context
@click.option("--diff", "-d", is_flag=True, help="Show diff of suggested changes")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def lint(
    ctx: click.Context,
    diff: bool,
    paths: Sequence[Path],
) -> None:
    """
    lint one or more paths and return suggestions

    pass "- <FILENAME>" for STDIN representing <FILENAME>
    """
    options: Options = ctx.obj

    if not paths:
        paths = [Path.cwd()]

    exit_code = 0
    visited: Set[Path] = set()
    dirty: Set[Path] = set()
    autofixes = 0
    config = generate_config(options=options)
    for result in fixit_paths(
        paths, options=options, metrics_hook=print if options.print_metrics else None
    ):
        visited.add(result.path)
        if print_result(
            result,
            show_diff=diff,
            output_format=config.output_format,
            output_template=config.output_template,
        ):
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
    help="how to apply fixes; interactive by default unless STDIN",
)
@click.option("--diff", "-d", is_flag=True, help="show diff even with --automatic")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def fix(
    ctx: click.Context,
    interactive: bool,
    diff: bool,
    paths: Sequence[Path],
) -> None:
    """
    lint and autofix one or more files and return results

    pass "- <FILENAME>" for STDIN representing <FILENAME>;
    this will ignore "--interactive" and always use "--automatic"
    """
    options: Options = ctx.obj

    if not paths:
        paths = [Path.cwd()]

    is_stdin = bool(paths[0] and str(paths[0]) == "-")
    interactive = interactive and not is_stdin
    autofix = not interactive
    exit_code = 0

    visited: Set[Path] = set()
    dirty: Set[Path] = set()
    autofixes = 0
    fixed = 0

    # TODO: make this parallel
    generator = capture(
        fixit_paths(
            paths,
            autofix=autofix,
            options=options,
            parallel=False,
            metrics_hook=print if options.print_metrics else None,
        )
    )
    config = generate_config(options=options)
    for result in generator:
        visited.add(result.path)
        # for STDIN, we need STDOUT to equal the fixed content, so
        # move everything else to STDERR
        if print_result(
            result,
            show_diff=interactive or diff,
            stderr=is_stdin,
            output_format=config.output_format,
            output_template=config.output_template,
        ):
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
                generator.respond(True)  # noqa: B038
                fixed += 1
            elif answer == "q":
                break

    splash(visited, dirty, autofixes, fixed)
    ctx.exit(exit_code)


@main.command()
@click.pass_context
@click.option("--stdio", type=bool, default=True, help="Serve LSP over stdio")
@click.option("--tcp", type=int, help="Port to serve LSP over")
@click.option("--ws", type=int, help="Port to serve WS over")
@click.option(
    "--debounce-interval",
    type=float,
    default=LSPOptions.debounce_interval,
    help="Delay in seconds for server-side debounce",
)
def lsp(
    ctx: click.Context,
    stdio: bool,
    tcp: Optional[int],
    ws: Optional[int],
    debounce_interval: float,
) -> None:
    """
    Start server for:
    https://microsoft.github.io/language-server-protocol/
    """
    from .lsp import LSP

    main_options = ctx.obj
    lsp_options = LSPOptions(
        tcp=tcp,
        ws=ws,
        stdio=stdio,
        debounce_interval=debounce_interval,
    )
    LSP(main_options, lsp_options).start()


@main.command()
@click.pass_context
@click.argument("rules", nargs=-1, required=True, type=str)
def test(ctx: click.Context, rules: Sequence[str]) -> None:
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
def upgrade(ctx: click.Context, paths: Sequence[Path]) -> None:
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
def debug(ctx: click.Context, paths: Sequence[Path]) -> None:
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


@main.command(name="validate-config")
@click.pass_context
@click.argument("path", nargs=1, type=click.Path(exists=True, path_type=Path))
def validate_config_command(ctx: click.Context, path: Path) -> None:
    """
    validate the config provided
    """
    exceptions = validate_config(path)

    try:
        from rich import print as pprint
    except ImportError:
        from pprint import pprint  # type: ignore

    if exceptions:
        for e in exceptions:
            pprint(e)
        exit(-1)
