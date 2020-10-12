# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Usage:
#
#   $ fixit run_rules --help
#   $ fixit apply_fix --help
#   $ fixit insert_suppressions --help
#   $ fixit add_new_rule --help

import argparse
import importlib.util
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from typing import List

from absl import app
from absl.flags import argparse_flags

from fixit.cli import add_new_rule, apply_fix, insert_suppressions, run_rules


def get_fixit_version() -> str:
    """Get current Fixit's version"""
    directory = Path(__file__).resolve().parents[1]

    spec: ModuleSpec = importlib.util.spec_from_file_location(
        "version", directory / "_version.py"
    )

    version: ModuleType = importlib.util.module_from_spec(spec)
    # pyre-ignore Pyre doesn't know about importlib entirely.
    spec.loader.exec_module(version)
    # pyre-ignore Pyre has no way of knowing that this constant exists.
    return version.FIXIT_VERSION


def _parse_flags(argv: List[str]) -> argparse.Namespace:
    """Command lines flag parsing."""
    parser = argparse_flags.ArgumentParser(
        prog="fixit",
        description="These are common Fixit commands used in various situations:",
    )

    parser.add_argument("--version", action="version", version=get_fixit_version())
    parser.set_defaults(subparser_fn=lambda _: parser.print_help())

    # Register sub-commands
    subparser = parser.add_subparsers(title="command")

    add_new_rule.register_subparser(subparser)
    run_rules.register_subparser(subparser)
    apply_fix.register_subparser(subparser)
    insert_suppressions.register_subparser(subparser)

    return parser.parse_args(argv[1:])


def main(args: argparse.Namespace) -> None:
    # Launch the subcommand defined in the subparser (or default to print help)
    args.subparser_fn(args)


def launch_cli() -> None:
    """Parse arguments and launch the CLI main function."""
    app.run(main, flags_parser=_parse_flags)


if __name__ == "__main__":
    launch_cli()
