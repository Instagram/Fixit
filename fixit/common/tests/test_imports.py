# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
import shutil
from pathlib import Path

from libcst.testing.utils import UnitTest

from fixit.common.config import (
    CACHE as CONFIG_CACHE,
    get_lint_config,
    get_rules_for_path,
)
from fixit.common.utils import (
    dedent_with_lstrip,
    DuplicateLintRuleNameError,
    find_and_import_rule,
    import_rule_from_package,
    LintRuleNotFoundError,
)


DUMMY_PACKAGE: str = "fixit.common.tests.test_imports_dummy_package"
DUMMY_PACKAGE_PATH: Path = Path(__file__).parent / "test_imports_dummy_package"

DUPLICATE_DUMMY_PATH: Path = (
    Path(__file__).parent / "test_imports_dummy_package_with_duplicate_rule"
)

# Using dummy config file, test whether the rule import helpers work as expected.
class ImportsTest(UnitTest):
    def test_get_rules_from_config(self) -> None:
        rules = get_rules_for_path(DUMMY_PACKAGE_PATH)
        expected_rules = {
            f"{DUMMY_PACKAGE}.dummy_1",
            f"{DUMMY_PACKAGE}.dummy_2",
            f"{DUMMY_PACKAGE}.dummy_3",
        }
        self.assertEqual(expected_rules, {r.__module__ for r in rules})

    def test_get_rules_from_config_with_duplicate(self) -> None:
        with self.assertRaises(DuplicateLintRuleNameError):
            get_rules_for_path(
                DUPLICATE_DUMMY_PATH / "subpackage_defining_duplicate_rule" / "dummy.py"
            )

    def test_import_rule_from_package(self) -> None:
        rules_package = get_lint_config(DUMMY_PACKAGE_PATH).packages
        self.assertEqual(rules_package, [DUMMY_PACKAGE])

        # Test with an existing dummy rule.
        imported_rule = import_rule_from_package(rules_package[0], "DummyRule2")
        self.assertIsNotNone(imported_rule)
        self.assertEqual(imported_rule.__name__, "DummyRule2")
        self.assertEqual(imported_rule.__module__, f"{DUMMY_PACKAGE}.dummy_2")

        # Test with non-existent rule.
        imported_rule = import_rule_from_package(rules_package[0], "DummyRule1000")
        self.assertIsNone(imported_rule)

    def test_find_and_import_rule(self) -> None:
        rules_packages = get_lint_config(DUMMY_PACKAGE_PATH).packages

        # Test with existing dummy rule. Should get the first one it finds, from dummy_1 module.
        imported_rule = find_and_import_rule("DummyRule1", rules_packages)
        self.assertEqual(imported_rule.__module__, f"{DUMMY_PACKAGE}.dummy_1")

        with self.assertRaises(LintRuleNotFoundError):
            imported_rule = find_and_import_rule("DummyRule1000", rules_packages)


class NestedTest(UnitTest):
    def test_nested_rule_no_inherit_does_not_inherit(self) -> None:
        rules = get_rules_for_path(DUMMY_PACKAGE_PATH / "nested_no_inherit")
        expected_rules = {
            f"{DUMMY_PACKAGE}.dummy_2",
        }
        self.assertEqual(expected_rules, {r.__module__ for r in rules})

    def test_nested_rule_inherit_does_inherit(self) -> None:
        CONFIG_CACHE.clear()
        rules = get_rules_for_path(DUMMY_PACKAGE_PATH / "nested_inherit")
        expected_rules = {
            f"{DUMMY_PACKAGE}.dummy_1",
            f"{DUMMY_PACKAGE}.dummy_3",
        }
        self.assertEqual(expected_rules, {r.__module__ for r in rules})
