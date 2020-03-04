# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import ast
import re
from pathlib import Path
from typing import Any, Mapping, Pattern, Union


REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent.parent.parent
DISTILLERY_ROOT: Path = REPO_ROOT / "distillery"

# Any file with these raw bytes should be ignored
BYTE_MARKER_IGNORE_ALL_REGEXP: Pattern[bytes] = re.compile(rb"@(generated|nolint)")

# https://gitlab.com/pycqa/flake8/blob/9631dac52aa6ed8a3de9d0983c/src/flake8/defaults.py
NOQA_INLINE_REGEXP: Pattern[str] = re.compile(
    # We're looking for items that look like this:
    # ``# noqa``
    # ``# noqa: E123``
    # ``# noqa: E123,W451,F921``
    # ``# NoQA: E123,W451,F921``
    # ``# NOQA: E123,W451,F921``
    # We do not care about the ``: `` that follows ``noqa``
    # We do not care about the casing of ``noqa``
    # We want a comma-separated list of errors
    # TODO; support non-numerical lint codes
    r"# noqa(?!-file)(?:: (?P<codes>([A-Z]+[0-9]+(?:[,\s]+)?)+))?",
    re.IGNORECASE,
)
LINT_IGNORE_REGEXP: Pattern[str] = re.compile(
    # We're looking for items that look like this:
    # ``# lint-fixme: IG00``
    # ``# lint-fixme: IG00: Details``
    # ``# lint-fixme: IG01, IG02: Details``
    # TODO: support non-numerical lint codes
    r"# lint-(?:ignore|fixme)"
    + r": (?P<codes>([-_a-zA-Z0-9]+,\s*)*[-_a-zA-Z0-9]+)"
    + r"(?:: (?P<reason>.+))?"
)

# Skip evaluation of the given file.
# People should use `# noqa-file` or `@no- lint` instead. This is here for compatibility
# with Flake8.
FLAKE8_NOQA_FILE: Pattern[str] = re.compile(r"# flake8[:=]\s*noqa", re.IGNORECASE)

# Skip evaluation of a given rule for a given file
# `# noqa-file: IG02: Some reason why we can't use this rule`
# `# noqa-file: IG02,IG52: Some reason why we can't use these rules`
#
# TODO: Be a bit more lenient with parsing, and surface useful error messages when
# looking at the comments. E.g. It's not obvious right now that a reason must be
# specified.
NOQA_FILE_RULE: Pattern[str] = re.compile(
    r"# noqa-file: "
    + r"(?P<codes>([-_a-zA-Z0-9]+,\s*)*[-_a-zA-Z0-9]+): "
    + r"(?P<reason>.+)"
)


def _eval_python_config(source: str) -> Mapping[str, Any]:
    """
    Given the contents of a __lint__.py file, calls `ast.literal_eval`.

    We're using a python file because we want "json with comments". We should probably
    switch to yaml or toml at some point, but we don't have a way for the linter to pull
    in third-party dependencies yet. Python's ini support isn't flexible enough for our
    potential use-cases.

    We don't allow imports or arbitrary code because it's dangerous, could slow down the
    linter, and it'll make it harder to adjust the format of this file later and the
    execution environment.
    """
    tree = ast.parse(source)
    # Try to catch some common ways a user could mess things up, try to generate
    # better error messages than just a generic SyntaxError
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("__lint__.py file may not contain imports")
        if isinstance(node, ast.Call):
            raise ValueError("__lint__.py file may not contain function calls")
    if len(tree.body) != 1:
        raise ValueError("A __lint__.py file should contain a single expression")
    result = ast.literal_eval(source)
    if not isinstance(result, Mapping):
        raise ValueError("A __lint__.py file should contain a dictionary")
    return result


def get_config(filename: Union[str, Path]) -> Mapping[str, Any]:
    """
    Given the filename of a file being linted, searches for the closest __lint__.py
    file, and evaluates it.
    """
    # track previous_directory to avoid cases where we could end up with an infinite
    # loop due to a bad filename.
    previous_directory = None
    directory = (REPO_ROOT / filename).parent.resolve()
    while directory != REPO_ROOT and directory != previous_directory:

        possible_config = directory / "__lint__.py"
        if possible_config.is_file():
            with open(possible_config, "r") as f:
                return _eval_python_config(f.read())

        previous_directory = directory
        directory = directory.parent
    return {}
