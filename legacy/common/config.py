# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import distutils.spawn


try:
    import importlib.resources as pkg_resources
except ImportError:  # For <=3.6
    import importlib_resources as pkg_resources

import json
import os
import re
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Pattern, Set

import yaml
from jsonschema import validate

from fixit.common.base import LintConfig
from fixit.common.utils import import_distinct_rules_from_package, LintRuleCollectionT


LINT_CONFIG_FILE_NAME: Path = Path(".fixit.config.yaml")
LINT_CONFIG_SCHEMA_NAME: str = "config.schema.json"

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
    r"^# noqa(?!-file)(?:: (?P<codes>([a-zA-Z0-9]+,\s*)*[-_a-zA-Z0-9]+))?",
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

DEFAULT_FORMATTER = ["black", "-"]
PATH_SETTINGS = ["repo_root", "fixture_dir"]


def get_validated_settings(
    file_content: Dict[str, Any], current_dir: Path
) -> Dict[str, Any]:
    # __package__ should never be none (config.py should not be run directly)
    # But use .get() to make pyre happy
    pkg = globals().get("__package__")
    assert pkg, "No package was found, config types not validated."
    config = pkg_resources.read_text(pkg, LINT_CONFIG_SCHEMA_NAME)
    # Validates the types and presence of the keys
    schema = json.loads(config)
    validate(instance=file_content, schema=schema)

    for path_setting_name in PATH_SETTINGS:
        if path_setting_name in file_content:
            setting_value = file_content[path_setting_name]
            abspath: Path = (current_dir / setting_value).resolve()
        else:
            abspath: Path = current_dir
        # Set path setting to absolute path.
        file_content[path_setting_name] = str(abspath)

    return file_content


@lru_cache()
def get_lint_config() -> LintConfig:
    config = {}

    cwd = Path.cwd()
    for directory in (cwd, *cwd.parents):
        # Check for config file.
        # pyre-fixme[58]: `/` is not supported for operand types `object` and `Path`.
        possible_config = directory / LINT_CONFIG_FILE_NAME
        if possible_config.is_file():
            with open(possible_config, "r") as f:
                file_content = yaml.safe_load(f.read())

            if isinstance(file_content, dict):
                # pyre-fixme[6]: Expected `Path` for 2nd param but got `object`.
                config = get_validated_settings(file_content, directory)
                break

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
            package,
            lint_config.block_list_rules,
            all_names,
            lint_config.allow_list_rules,
        )
        rules.update(rules_from_pkg)
    return rules
