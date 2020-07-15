# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import ast
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Mapping, Optional, Pattern, Union

import yaml


FIXIT_ROOT: Path = Path(__file__).resolve().parent.parent
FIXTURE_DIRECTORY: Path = FIXIT_ROOT / "tests" / "fixtures"

LINT_CONFIG_FILE_NAME: Path = Path(".lint.config.yaml")

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


STRING_SETTINGS = ["generated_code_marker"]
LIST_SETTINGS = ["formatter", "blacklist_patterns", "blacklist_rules", "packages"]
PATH_SETTINGS = ["repo_root"]


@dataclass(frozen=False)
class LintConfig:
    generated_code_marker: str = f"@gen{''}erated"
    formatter: List[str] = field(default_factory=lambda: ["black", "-"])
    blacklist_patterns: List[str] = field(default_factory=list)
    blacklist_rules: List[str] = field(default_factory=list)
    packages: List[str] = field(default_factory=lambda: ["fixit.rules"])
    repo_root: str = "."


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


def get_context_config(filename: Union[str, Path]) -> Mapping[str, Any]:
    """
    Given the filename of a file being linted, searches for the closest __lint__.py
    file, and evaluates it.
    """
    current_dir = Path(filename).resolve().parent
    previous_dir: Optional[Path] = None
    while current_dir != previous_dir:
        # Check for config file.
        possible_config = current_dir / "__lint__.py"
        if possible_config.is_file():
            with open(possible_config, "r") as f:
                return _eval_python_config(f.read())

        # Try to go up a directory.
        previous_dir = current_dir
        current_dir = current_dir.parent
    return {}


def get_lint_config() -> LintConfig:
    config = LintConfig()
    current_dir = Path(os.getcwd())
    previous_dir: Optional[Path] = None
    while current_dir != previous_dir:
        # Check for config file.
        possible_config = current_dir / LINT_CONFIG_FILE_NAME
        if possible_config.is_file():
            with open(possible_config, "r") as f:
                file_content = yaml.safe_load(f.read())

            if isinstance(file_content, dict):
                for string_setting in STRING_SETTINGS:
                    if string_setting in file_content and isinstance(
                        file_content[string_setting], str
                    ):
                        setattr(config, string_setting, file_content[string_setting])
                for list_setting in LIST_SETTINGS:
                    if (
                        list_setting in file_content
                        and isinstance(file_content[list_setting], list)
                        and all(isinstance(s, str) for s in file_content[list_setting])
                    ):
                        setattr(config, list_setting, file_content[list_setting])
                for path_setting in PATH_SETTINGS:
                    if path_setting in file_content and isinstance(
                        file_content[path_setting], str
                    ):
                        # Resolve any relative paths to be absolute
                        setattr(
                            config,
                            path_setting,
                            str(Path(file_content[path_setting]).resolve()),
                        )
                return config

        # Try to go up a directory.
        previous_dir = current_dir
        current_dir = current_dir.parent
    # If not config file has been found, return the config with defaults.
    return config


def gen_config_file() -> None:
    # Generates a `.lint.config.yaml` file with defaults in the current working dir.
    config_file = LINT_CONFIG_FILE_NAME.resolve()
    default_config_dict = asdict(LintConfig())
    with open(config_file, "w") as cf:
        yaml.dump(default_config_dict, cf)
