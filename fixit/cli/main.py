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
import sys
from typing import List

from fixit._version import FIXIT_VERSION
from fixit.cli import add_new_rule, apply_fix, insert_suppressions, run_rules


def main(argv: List[str] = sys.argv[1:]) -> None:
    """Fixit CLI and its sub-commands"""
    parser = argparse.ArgumentParser(
        prog="fixit",
        description="These are common Fixit commands used in various situations:",
    )

    parser.add_argument("--version", action="version", version=FIXIT_VERSION)
    parser.set_defaults(subparser_fn=lambda _: parser.print_help())

    # Register sub-commands
    subparser = parser.add_subparsers(title="command")

    add_new_rule.register_subparser(subparser)
    apply_fix.register_subparser(subparser)
    insert_suppressions.register_subparser(subparser)
    run_rules.register_subparser(subparser)

    args = parser.parse_args(argv)
    args.subparser_fn(args)


if __name__ == "__main__":
    sys.exit(main())
