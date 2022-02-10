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
from typing import Any, Dict, Pattern, Set, Optional

import yaml
from jsonmerge import Merger
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
    schema = _get_config_schema()
    validate(instance=file_content, schema=schema)

    for path_setting_name in PATH_SETTINGS:
        if path_setting_name in file_content:
            setting_value = file_content[path_setting_name]
            abspath: Path = (current_dir / setting_value).resolve()
        else:
            abspath: Path = current_dir
        # Set path setting to absolute path.
        file_content[path_setting_name] = str(abspath)

    file_content["inherit"] = file_content.get("inherit", False)
    file_content["allow_list_rules"] = file_content.get("allow_list_rules", [])

    return file_content


@lru_cache()
def _get_config_schema() -> Dict[str, Any]:
    # __package__ should never be none (config.py should not be run directly)
    # But use .get() to make pyre happy
    pkg = globals().get("__package__")
    assert pkg, "No package was found, config types not validated."
    config = pkg_resources.read_text(pkg, LINT_CONFIG_SCHEMA_NAME)
    schema = json.loads(config)
    return schema

CACHE: Dict[Path, LintConfig] = {}

def get_lint_config(path: Optional[Path] = None) -> LintConfig:
    """
    Get configuration for linting a given path. If a path is provided we walk up
    the path and merge configurations along the way until `inherit` is set to `False`.
    """
    if path is None:
        directory = Path.cwd()
    elif not path.is_dir():
        directory = path.parent
    else:
        directory = path

    config = {}
    merger = Merger(_get_config_schema())

    current = directory
    while current.parent != current:
        if current in CACHE:
            return CACHE[current]

        config_path = current / LINT_CONFIG_FILE_NAME

        if config_path.is_file():
            content = yaml.safe_load(config_path.read_text())

            if isinstance(content, dict):
                local_config = get_validated_settings(content, current)
                config = merger.merge(config, local_config)
                if not local_config["inherit"]:
                    break

        previous = current
        current = current.parent

    # Find formatter executable if there is one.
    formatter_args = config.get("formatter", DEFAULT_FORMATTER)
    exe = distutils.spawn.find_executable(formatter_args[0]) or formatter_args[0]
    formatter_args[0] = os.path.abspath(exe)
    config["formatter"] = formatter_args

    result = LintConfig(**config)
    CACHE[directory] = result
    return result


def gen_config_file() -> None:
    # Generates a `.fixit.config.yaml` file with defaults in the current working dir.
    config_file = LINT_CONFIG_FILE_NAME.resolve()
    default_config_dict = asdict(LintConfig())
    with open(config_file, "w") as cf:
        yaml.dump(default_config_dict, cf)


def get_rules_for_path(path: Optional[Path]) -> LintRuleCollectionT:
    # Get rules from the packages specified in the lint config file, omitting block-listed rules.
    lint_config = get_lint_config(path)
    rules: LintRuleCollectionT = set()
    seen_names: Set[str] = set()
    for package in lint_config.packages:
        rules_from_pkg = import_distinct_rules_from_package(
            package,
            seen_names,
            lint_config.block_list_rules,
            lint_config.allow_list_rules,
        )
        rules.update(rules_from_pkg)
    return rules
