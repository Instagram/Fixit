# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import json
import os
import tempfile
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence, TypeVar, Union
from unittest import mock

from jsonschema.exceptions import ValidationError
from libcst.testing.utils import UnitTest

from fixit.common.config import _merge_lint_configs, get_validated_settings


ReturnType = TypeVar("ReturnType")

TEST_CONFIG: Dict[str, Union[Dict[str, Dict[str, List[str]]], List[str], bool, str]] = {
    "allow_list_rules": [],
    "formatter": ["black", "-", "--no-diff"],
    "packages": ["python.fixit.rules"],
    "block_list_rules": ["Flake8PseudoLintRule"],
    "fixture_dir": f"{os.getcwd()}",
    "repo_root": f"{os.getcwd()}",
    "use_noqa": False,
    "rule_config": {
        "UnusedImportsRule": {
            "ignored_unused_modules": [
                "__future__",
                "__static__",
                "__static__.compiler_flags",
                "__strict__",
            ]
        },
    },
    "inherit": False,
}


def with_temp_dir(func: Callable[..., ReturnType]) -> Callable[..., ReturnType]:
    @wraps(func)
    def wrapper(*args: Sequence[Any], **kwargs: Mapping[Any, Any]) -> ReturnType:
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(f"{temp_dir}/.fixit.config.yaml").write_text(json.dumps(TEST_CONFIG))
            Path(f"{temp_dir}/__init__").touch()
            sub_dir = Path(f"{temp_dir}/subdir")
            sub_dir.mkdir()
            (sub_dir / "__init__").touch()
            return func(*args, Path(temp_dir), sub_dir, **kwargs)

    return wrapper


class TestConfig(UnitTest):
    def setUp(self) -> None:
        patcher = mock.patch("fixit.common.config.Path.cwd")
        self.mock_cwd = patcher.start()
        self.addCleanup(patcher.stop)

    def test_validated_settings_with_bad_types(self) -> None:
        bad_config = {"block_list_rules": False}
        with self.assertRaisesRegex(ValidationError, "False is not of type 'array'"):
            get_validated_settings(bad_config, Path("."))

    def test_validated_settings_with_correct_types(self) -> None:
        config = {"block_list_rules": ["FakeRule"]}
        settings = get_validated_settings(config, Path("."))
        self.assertEqual(
            {
                "allow_list_rules": [],
                "block_list_rules": ["FakeRule"],
                "fixture_dir": ".",
                "repo_root": ".",
                "inherit": False,
            },
            settings,
        )

    def test_validated_settings_all_keys(self) -> None:
        settings = get_validated_settings(TEST_CONFIG, Path("."))
        self.assertEqual(
            TEST_CONFIG,
            settings,
        )

    @with_temp_dir
    def test_merge_lint_configs_simple(self, temp_dir: Path, sub_dir: Path) -> None:
        self.mock_cwd.return_value = sub_dir
        test_config_2 = {
            "allow_list_rules": ["FakeRule"],
            "block_list_rules": ["BlockedRule"],
            "formatter": ["fakeformatter"],
            "use_noqa": True,
            "inherit": True,
        }
        (sub_dir / ".fixit.config.yaml").write_text(json.dumps(test_config_2))
        expected_merged_config = {
            "allow_list_rules": ["FakeRule"],  # appended
            "formatter": ["black", "-", "--no-diff", "fakeformatter"],  # appended
            "packages": ["python.fixit.rules"],  # inherited
            "block_list_rules": ["Flake8PseudoLintRule", "BlockedRule"],  # appended
            "fixture_dir": f"{sub_dir}",  # inherited
            "repo_root": f"{sub_dir}",  # inherited
            "rule_config": {  # inherited
                "UnusedImportsRule": {
                    "ignored_unused_modules": [
                        "__future__",
                        "__static__",
                        "__static__.compiler_flags",
                        "__strict__",
                    ]
                },
            },
            "use_noqa": True,  # overridden
            "inherit": True,  # overridden
        }
        merged_config = _merge_lint_configs()
        self.assertEqual(expected_merged_config, merged_config)

    @with_temp_dir
    def test_merge_lint_configs_rule_config_new_rule(
        self, temp_dir: Path, sub_dir: Path
    ) -> None:
        self.mock_cwd.return_value = sub_dir
        test_config_2 = {
            "rule_config": {"TestingRule": {"a_config_setting": True}},
            "inherit": True,
        }
        (sub_dir / ".fixit.config.yaml").write_text(json.dumps(test_config_2))
        expected_merged_config = {
            "allow_list_rules": [],
            "formatter": ["black", "-", "--no-diff"],
            "packages": ["python.fixit.rules"],
            "block_list_rules": ["Flake8PseudoLintRule"],
            "fixture_dir": f"{sub_dir}",
            "repo_root": f"{sub_dir}",
            "rule_config": {
                "UnusedImportsRule": {
                    "ignored_unused_modules": [
                        "__future__",
                        "__static__",
                        "__static__.compiler_flags",
                        "__strict__",
                    ]
                },
                "TestingRule": {"a_config_setting": True},
            },
            "use_noqa": False,
            "inherit": True,
        }
        merged_config = _merge_lint_configs()
        self.assertEqual(expected_merged_config, merged_config)

    @with_temp_dir
    def test_merge_lint_configs_rule_config_override_rule(
        self, temp_dir: Path, sub_dir: Path
    ) -> None:
        self.mock_cwd.return_value = sub_dir
        test_config_2 = {
            "rule_config": {
                "UnusedImportsRule": {"ignored_unused_modules": ["__init__"]}
            },
            "inherit": True,
        }
        (sub_dir / ".fixit.config.yaml").write_text(json.dumps(test_config_2))
        expected_merged_config = {
            "allow_list_rules": [],
            "formatter": ["black", "-", "--no-diff"],
            "packages": ["python.fixit.rules"],
            "block_list_rules": ["Flake8PseudoLintRule"],
            "fixture_dir": f"{sub_dir}",
            "repo_root": f"{sub_dir}",
            "rule_config": {
                "UnusedImportsRule": {"ignored_unused_modules": ["__init__"]}
            },
            "use_noqa": False,
            "inherit": True,
        }
        merged_config = _merge_lint_configs()
        self.assertEqual(expected_merged_config, merged_config)

    @with_temp_dir
    @mock.patch("fixit.common.config._get_config_schema")
    def test_merge_lint_configs_missing_schema(
        self, temp_dir: Path, sub_dir: Path, mock_schema: mock.Mock
    ) -> None:
        self.mock_cwd.return_value = sub_dir
        mock_schema.return_value = None
        test_config_2 = {"block_list_rules": ["NotMerged"], "inherit": True}
        (sub_dir / ".fixit.config.yaml").write_text(json.dumps(test_config_2))
        merged_config = _merge_lint_configs()
        # Returns the first LintConfig found (the lowest leaf)
        self.assertEqual(merged_config["block_list_rules"], ["NotMerged"])
        self.assertEqual(merged_config["inherit"], True)

    @with_temp_dir
    def test_merge_lint_configs_inherit_false(
        self, temp_dir: Path, sub_dir: Path
    ) -> None:
        self.mock_cwd.return_value = sub_dir
        test_config_2 = {"block_list_rules": ["NotMerged"], "inherit": False}
        (sub_dir / ".fixit.config.yaml").write_text(json.dumps(test_config_2))
        merged_config = _merge_lint_configs()
        # Returns the first LintConfig found (the lowest leaf)
        self.assertEqual(merged_config["block_list_rules"], ["NotMerged"])
        self.assertEqual(merged_config["inherit"], False)


# TODO: lisroach think of more tests to add here
