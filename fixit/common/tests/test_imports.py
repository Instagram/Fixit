# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
from pathlib import Path

from libcst.testing.utils import UnitTest

from fixit.common.config import get_lint_config, get_rules_from_config
from fixit.common.utils import (
    DuplicateLintRuleNameError,
    LintRuleNotFoundError,
    find_and_import_rule,
    import_rule_from_package,
)


DUMMY_PACKAGE: str = "fixit.common.tests.dummy_package"
DUMMY_SUBPACKAGE: str = "fixit.common.tests.dummy_package.dummy_subpackage"


# Using dummy config file, test whether the rule import helpers work as expected.
class ImportsTest(UnitTest):
    def setUp(self) -> None:
        # We need to change the working directory so that the dummy config file is used.
        self.old_wd = os.getcwd()
        test_dir = Path(__file__).parent
        os.chdir(test_dir)

        # We also need to clear the lru_cache for the get_lint_config function between tests.
        getattr(get_lint_config, "cache_clear")()

    def tearDown(self) -> None:
        # Need to change back to original working directory so that we don't mess with other unit tests.
        os.chdir(self.old_wd)
        getattr(get_lint_config, "cache_clear")()

    def test_get_rules_from_config(self) -> None:
        with self.assertRaises(DuplicateLintRuleNameError):
            # We have two dummy lint rules with the same name. Verify this raises an error.
            get_rules_from_config()

        # Now try to import all rules from a package where there aren't any duplicates.
        getattr(get_lint_config, "cache_clear")()
        next_dir = os.path.join(os.getcwd(), "dummy_package")
        os.chdir(next_dir)
        rules = get_rules_from_config()

        # Assert all rules are imported as expected.
        self.assertEqual(len(rules), 3)
        self.assertTrue(all(r.__module__ == f"{DUMMY_SUBPACKAGE}.dummy" for r in rules))

    def test_import_rule_from_package(self) -> None:
        rules_package = get_lint_config().packages
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
        rules_packages = get_lint_config().packages

        # Test with existing dummy rule. Should get the first one it finds, from dummy_1 module.
        imported_rule = find_and_import_rule("DummyRule1", rules_packages)
        self.assertEqual(imported_rule.__module__, f"{DUMMY_PACKAGE}.dummy_1")

        with self.assertRaises(LintRuleNotFoundError):
            imported_rule = find_and_import_rule("DummyRule1000", rules_packages)
