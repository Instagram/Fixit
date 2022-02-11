# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
from pathlib import Path

from jsonschema.exceptions import ValidationError
from libcst.testing.utils import UnitTest

from fixit.common.config import get_validated_settings


TEST_CONFIG = {
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
}


class TestConfig(UnitTest):
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
                "inherit": False,
                "repo_root": ".",
            },
            settings,
        )

    def test_validated_settings_all_keys(self) -> None:
        self.maxDiff = None
        config = {
            "formatter": ["black", "-", "--no-diff"],
            "packages": ["python.fixit.rules"],
            "block_list_rules": ["Flake8PseudoLintRule"],
            "fixture_dir": f"{os.getcwd()}",
            "repo_root": f"{os.getcwd()}",
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
        }
        settings = get_validated_settings(config, Path("."))
        self.assertEqual(
            config,
            settings,
        )
