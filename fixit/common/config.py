# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import ast
import distutils.spawn
import os
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Pattern, Union

import yaml


LINT_CONFIG_FILE_NAME: Path = Path(".fixit.config.yaml")

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


LIST_SETTINGS = ["formatter", "block_list_patterns", "block_list_rules", "packages"]
PATH_SETTINGS = ["repo_root"]
DEFAULT_FORMATTER = ["black", "-"]


@dataclass(frozen=True)
class LintConfig:
    formatter: List[str] = field(default_factory=lambda: DEFAULT_FORMATTER)
    # TODO: add block_list_patterns logic to lint rule engine/ipc.
    block_list_patterns: List[str] = field(default_factory=list)
    block_list_rules: List[str] = field(default_factory=list)
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


def get_validated_settings(
    file_content: Dict[str, Any], current_dir: Path
) -> Dict[str, Any]:
    settings = {}
    for list_setting in LIST_SETTINGS:
        if list_setting in file_content:
            if not (
                isinstance(file_content[list_setting], list)
                and all(isinstance(s, str) for s in file_content[list_setting])
            ):
                raise TypeError(
                    f"Expected list of strings for `{list_setting}` setting."
                )
            settings[list_setting] = file_content[list_setting]
    for path_setting in PATH_SETTINGS:
        if path_setting in file_content:
            setting_value = file_content[path_setting]
            if not isinstance(setting_value, str):
                raise TypeError(f"Expected string for `{path_setting}` setting.")
            abspath: Path = (current_dir / setting_value).resolve()
        else:
            abspath: Path = current_dir
        # Set path setting to absolute path.
        settings[path_setting] = str(abspath)
    return settings


@lru_cache()
def get_lint_config() -> LintConfig:
    config = {}
    current_dir = Path.cwd()
    previous_dir: Optional[Path] = None
    while current_dir != previous_dir:
        # Check for config file.
        possible_config = current_dir / LINT_CONFIG_FILE_NAME
        if possible_config.is_file():
            with open(possible_config, "r") as f:
                file_content = yaml.safe_load(f.read())

            if isinstance(file_content, dict):
                config = get_validated_settings(file_content, current_dir)
                break

        # Try to go up a directory.
        previous_dir = current_dir
        current_dir = current_dir.parent

    # Find formatter executable if there is one.
    formatter_args = config.get("formatter", DEFAULT_FORMATTER)
    exe = distutils.spawn.find_executable(formatter_args[0]) or formatter_args[0]
    config["formatter"][0] = os.path.abspath(exe)

    # Missing settings will be populated with defaults.
    return LintConfig(**config)


def gen_config_file() -> None:
    # Generates a `.fixit.config.yaml` file with defaults in the current working dir.
    config_file = LINT_CONFIG_FILE_NAME.resolve()
    default_config_dict = asdict(LintConfig())
    with open(config_file, "w") as cf:
        yaml.dump(default_config_dict, cf)
