# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
from pathlib import Path

from jsonschema.exceptions import ValidationError
from libcst.testing.utils import UnitTest

from fixit.common.config import get_validated_settings


class TestConfig(UnitTest):
    def test_validated_settings_with_bad_types(self) -> None:
        bad_config = {"block_list_rules": False}
        with self.assertRaises(ValidationError) as ex:
            get_validated_settings(bad_config, Path("."))
        self.assertIn("False is not of type 'array'", str(ex.exception))

    def test_validated_settings_with_correct_types(self) -> None:
        config = {"block_list_rules": ["FakeRule"]}
        settings = get_validated_settings(config, Path("."))
        self.assertEqual(
            {"block_list_rules": ["FakeRule"], "fixture_dir": ".", "repo_root": "."},
            settings,
        )

    def test_validated_settings_all_keys(self) -> None:
        config = {
            "formatter": ["black", "-", "--no-diff"],
            "packages": ["python.fixit.rules"],
            "block_list_rules": ["Flake8PseudoLintRule"],
            "fixture_dir": "/fake/path",
            "repo_root": "/fake/path",
            "rule_config": {
                "UnusedImportsRule": {
                    "ignored_unused_modules": [
                        "__future__",
                        "__static__",
                        "__static__.compiler_flags",
                        "__strict__",
                    ]
                },
                "NoBadCallsRule": {
                    "badCalls": {
                        "calls": [
                            "os.spawnl",
                            "os.spawnle",
                            "os.spawnlp",
                            "os.spawnlpe",
                            "os.spawnv",
                            "os.spawnve",
                            "os.spawnvp",
                            "os.spawnvpe",
                        ],
                        "why": """Using `os.spawn*` is deprecated. Use `subprocess` instead.\
                    See https://www.python.org/dev/peps/pep-0324/#replacing-os-spawn for more\
                    information.""",
                    }
                },
            },
        }
        settings = get_validated_settings(config, Path("."))
        self.assertEqual(
            config,
            settings,
        )
