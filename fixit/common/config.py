# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import distutils.spawn
import os
import re
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Pattern, Set

import yaml

from fixit.common.base import LintConfig
from fixit.common.utils import LintRuleCollectionT, import_distinct_rules_from_package


LINT_CONFIG_FILE_NAME: Path = Path(".fixit.config.yaml")

# https://gitlab.com/pycqa/flake8/blob/9631dac52aa6ed8a3de9d0983c/src/flake8/defaults.py
NOQA_INLINE_REGEXP: Pattern[str] = re.compile(
    # TODO: Deprecate
    # We're looking for items that look like this:
    # ``# noqa``
    # ``# noqa: E123``
    # ``# noqa: E123,W451,F921``
    # ``# NoQA: E123,W451,F921``
    # ``# NOQA: E123,W451,F921``
    # We do not care about the ``: `` that follows ``noqa``
    # We do not care about the casing of ``noqa``
    # We want a comma-separated list of errors
    r"# noqa(?!-file)(?:: (?P<codes>([a-zA-Z0-9]+,\s*)*[-_a-zA-Z0-9]+))?",
    re.IGNORECASE,
)
LINT_IGNORE_REGEXP: Pattern[str] = re.compile(
    # We're looking for items that look like this:
    # ``# lint-fixme: LintRuleName``
    # ``# lint-fixme: LintRuleName: Details``
    # ``# lint-fixme: LintRuleName1, LintRuleName2: Details``
    r"# lint-(ignore|fixme)"
    + r": (?P<codes>([-_a-zA-Z0-9]+,\s*)*[-_a-zA-Z0-9]+)"
    + r"(:( (?P<reason>.+)?)?)?"
)

# Skip evaluation of the given file.
# People should use `# noqa-file` or `@no- lint` instead. This is here for compatibility
# with Flake8.
FLAKE8_NOQA_FILE: Pattern[str] = re.compile(r"# flake8[:=]\s*noqa", re.IGNORECASE)

# Skip evaluation of a given rule for a given file
# `# noqa-file: LintRuleName: Some reason why we can't use this rule`
# `# noqa-file: LintRuleName,LintRuleName2: Some reason why we can't use these rules`
#
# TODO: Deprecate
NOQA_FILE_RULE: Pattern[str] = re.compile(
    r"# noqa-file: "
    + r"(?P<codes>([-_a-zA-Z0-9]+,\s*)*[-_a-zA-Z0-9]+): "
    + r"(?P<reason>.+)"
)


def _remove_capturing_groups(regex: bytes) -> bytes:
    return re.sub(rb"\?P<\w+>", b"", regex)


HAS_LINT_IGNORE_REGEXP: Pattern[bytes] = re.compile(LINT_IGNORE_REGEXP.pattern.encode())
HAS_LINT_IGNORE_OR_NOQA_REGEXP: Pattern[bytes] = re.compile(
    b"|".join(
        [
            _remove_capturing_groups(LINT_IGNORE_REGEXP.pattern.encode()),
            _remove_capturing_groups(NOQA_INLINE_REGEXP.pattern.encode()),
            _remove_capturing_groups(NOQA_FILE_RULE.pattern.encode()),
            _remove_capturing_groups(FLAKE8_NOQA_FILE.pattern.encode()),
        ]
    ),
    re.IGNORECASE,
)

LIST_SETTINGS = ["formatter", "block_list_patterns", "block_list_rules", "packages"]
PATH_SETTINGS = ["repo_root", "fixture_dir"]
NESTED_SETTINGS = ["rule_config"]
DEFAULT_FORMATTER = ["black", "-"]


def get_validated_settings(
    file_content: Dict[str, Any], current_dir: Path
) -> Dict[str, Any]:
    settings = {}
    for list_setting_name in LIST_SETTINGS:
        if list_setting_name in file_content:
            if not (
                isinstance(file_content[list_setting_name], list)
                and all(isinstance(s, str) for s in file_content[list_setting_name])
            ):
                raise TypeError(
                    f"Expected list of strings for `{list_setting_name}` setting."
                )
            settings[list_setting_name] = file_content[list_setting_name]
    for path_setting_name in PATH_SETTINGS:
        if path_setting_name in file_content:
            setting_value = file_content[path_setting_name]
            if not isinstance(setting_value, str):
                raise TypeError(f"Expected string for `{path_setting_name}` setting.")
            abspath: Path = (current_dir / setting_value).resolve()
        else:
            abspath: Path = current_dir
        # Set path setting to absolute path.
        settings[path_setting_name] = str(abspath)

    for nested_setting_name in NESTED_SETTINGS:
        if nested_setting_name in file_content:
            nested_setting = file_content[nested_setting_name]
            if not isinstance(nested_setting, dict):
                raise TypeError(
                    f"Expected key-value pairs for `{nested_setting_name}` setting."
                )
            settings[nested_setting_name] = {}
            # Verify that each setting is also a mapping
            for k, v in nested_setting.items():
                if not isinstance(v, dict):
                    raise TypeError(
                        f"Expected key-value pairs for `{v}` setting in {nested_setting_name}."
                    )
                settings[nested_setting_name].update({k: v})

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
    formatter_args[0] = os.path.abspath(exe)
    config["formatter"] = formatter_args

    # Missing settings will be populated with defaults.
    return LintConfig(**config)


def gen_config_file() -> None:
    # Generates a `.fixit.config.yaml` file with defaults in the current working dir.
    config_file = LINT_CONFIG_FILE_NAME.resolve()
    default_config_dict = asdict(LintConfig())
    with open(config_file, "w") as cf:
        yaml.dump(default_config_dict, cf)


def get_rules_from_config() -> LintRuleCollectionT:
    # Get rules from the packages specified in the lint config file, omitting block-listed rules.
    lint_config = get_lint_config()
    rules: LintRuleCollectionT = set()
    all_names: Set[str] = set()
    for package in lint_config.packages:
        rules_from_pkg = import_distinct_rules_from_package(
            package, lint_config.block_list_rules, all_names
        )
        rules.update(rules_from_pkg)
    return rules
