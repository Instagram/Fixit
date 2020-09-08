# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Usage:
#
#   $ python -m fixit.cli.add_new_rule --help
#   $ python -m fixit.cli.add_new_rule
#   $ python -m fixit.cli.add_new_rule --path fixit/rules/new_rule.py

import argparse
from pathlib import Path

from libcst.codemod._cli import invoke_formatter

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
class Rule(CstLintRule):
    \"""
    docstring or new_rule description
    \"""

    MESSAGE = "Enter rule description message"

    VALID = [Valid("'example'")]

    INVALID = [Invalid("'example'")]
"""


def is_path_exists(path: str) -> Path:
    """Check for valid path, if yes, return `Path` else raise `Error` """
    filepath = Path(path)
    if filepath.exists():
        raise FileNotFoundError(f"{filepath} already exists")
    elif not filepath.parent.exists():
        raise TypeError(f"{filepath} is not a valid path, provide path with file name")
    else:
        return filepath


def create_rule_file(file_path: Path) -> None:
    """Create a new rule file."""
    context = _LICENCE + _IMPORTS + _TO_DOS + _RULE_CLASS
    updated_context = invoke_formatter(get_lint_config().formatter, context)

    with open(file_path, "w") as f:
        f.write(updated_context)

    print(f"Successfully created {file_path.name} rule file at {file_path.parent}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Creates a skeleton of adding new rule file"
    )
    parser.add_argument(
        "-p",
        "--path",
        type=is_path_exists,
        default=Path("fixit/rules/new_rule.py"),
        help="Path to add rule file, Default is fixit/rules/new_rule.py",
    )

    args = parser.parse_args()
    create_rule_file(args.path)


if __name__ == "__main__":
    main()
