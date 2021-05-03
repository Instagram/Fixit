# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import itertools
import os
from pathlib import Path

from libcst.testing.utils import UnitTest

from fixit.common.config import (
    BOOLEAN_SETTINGS,
    LIST_SETTINGS,
    NESTED_SETTINGS,
    PATH_SETTINGS,
    get_validated_settings,
)


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
    def test_get_validated_settings(self) -> None:
        settings = get_validated_settings(TEST_CONFIG, Path("."))
        settings_options = list(
            itertools.chain(
                BOOLEAN_SETTINGS, LIST_SETTINGS, PATH_SETTINGS, NESTED_SETTINGS
            )
        )
        # Assert all the settings are set
        self.assertTrue(all(setting in settings_options for setting in settings.keys()))

    def test_get_validated_settings_raises_type_error(self) -> None:
        TEST_CONFIG["use_noqa"] = "Yes"  # set the wrong type
        with self.assertRaisesRegex(
            TypeError, r"Expected boolean for `use_noqa` setting\."
        ):
            get_validated_settings(TEST_CONFIG, Path("."))
