# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import sys
from pathlib import Path
from typing import Iterable, Optional

import click

from fixit import __version__

from .api import fixit_paths, print_result
from .config import collect_rules, generate_config
from .ftypes import Options


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
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def lint(
    ctx: click.Context,
    paths: Iterable[Path],
):
    """
    lint one or more paths and return suggestions
    """
    for result in fixit_paths(paths):
        print_result(result, ctx.obj.debug)


@main.command()
@click.pass_context
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def fix(
    ctx: click.Context,
    paths: Iterable[Path],
):
    """
    lint and autofix one or more files and return results
    """
    ctx.fail("not implemented yet")


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
