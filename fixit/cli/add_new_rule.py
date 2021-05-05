# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Usage:
#
#   $ python -m fixit.cli.add_new_rule --help
#   $ python -m fixit.cli.add_new_rule
#   $ python -m fixit.cli.add_new_rule --path fixit/rules/new_rule.py --name rule_name

import argparse
import sys
from pathlib import Path
from typing import Optional

from libcst.codemod._cli import invoke_formatter

from fixit.cli.utils import snake_to_camelcase
from fixit.common.config import get_lint_config


_LICENCE = """# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""

_IMPORTS = """
import libcst as cst
import libcst.matchers as m

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid

"""

_TO_DOS = """
\"""
This is a model rule file for adding a new rule to fixit module
\"""

"""

_RULE_CLASS = """
class {class_name}Rule(CstLintRule):
    \"""
    docstring or new_rule description
    \"""

    MESSAGE = "Enter rule description message"

    VALID = [Valid("'example'")]

    INVALID = [Invalid("'example'")]
"""


def is_path_exists(path: str) -> Path:
    """Check for valid path, if yes, return `Path` else raise `Error`"""
    filepath = Path(path)
    if filepath.exists():
        raise FileExistsError(f"{filepath} already exists")
    elif not filepath.parent.exists():
        raise TypeError(f"{filepath} is not a valid path, provide path with file name")
    else:
        return filepath


def is_valid_name(name: str) -> str:
    """Check for valid rule name"""
    if name.casefold().endswith(("rule", "rules")):
        raise ValueError("Please enter rule name without the suffix, 'rule' or 'Rule'")
    return snake_to_camelcase(name)


def create_rule_file(file_path: Path, rule_name: str) -> None:
    """Create a new rule file."""
    rule_name = is_valid_name(rule_name)
    context = _LICENCE + _IMPORTS + _TO_DOS + _RULE_CLASS
    updated_context = invoke_formatter(
        get_lint_config().formatter, context.format(class_name=rule_name)
    )

    with open(file_path, "w") as f:
        f.write(updated_context)

    print(f"Successfully created {file_path.name} rule file at {file_path.parent}")


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    """All required arguments for `add_new_rule`"""
    parser.add_argument(
        "--path",
        type=is_path_exists,
        default=Path("fixit/rules/new.py"),
        help="Path to add rule file, defaults to fixit/rules/new.py",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="",
        help="Name of the rule, defaults to `New`",
    )


def register_subparser(parser: Optional[argparse._SubParsersAction] = None) -> None:
    """Add parser or subparser for `add_new_rule` command."""
    if parser is None:
        add_rule_parser = argparse.ArgumentParser(
            description="Creates a skeleton of adding new rule file",
        )
        _add_arguments(add_rule_parser)
        sys.exit(_main(add_rule_parser.parse_args()))

    else:
        add_rule_parser = parser.add_parser(
            "add_new_rule",
            description="Creates a skeleton of adding new rule file.",
            help="Creates a skeleton of adding new rule file.",
        )
        _add_arguments(add_rule_parser)
        add_rule_parser.set_defaults(subparser_fn=_main)


def _main(args: argparse.Namespace) -> int:
    file_path = args.path
    rule_name = args.name if args.name else file_path.stem
    create_rule_file(file_path, rule_name)

    return 0


if __name__ == "__main__":
    register_subparser()
