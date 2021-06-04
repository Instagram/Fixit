# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import json
import os
import shutil
from pathlib import Path

from libcst.testing.utils import UnitTest

from fixit.common.config import (
    _merge_lint_configs,
    get_lint_config,
    get_rules_from_config,
)
from fixit.common.utils import (
    DuplicateLintRuleNameError,
    LintRuleNotFoundError,
    dedent_with_lstrip,
    find_and_import_rule,
    import_rule_from_package,
)


DUMMY_PACKAGE: str = "fixit.common.tests.dummy_package"
DUMMY_SUBPACKAGE: str = "fixit.common.tests.dummy_package.dummy_subpackage"
DUMMY_CONFIG_PATH: str = ".fixit.config.yaml"
DUMMY_SUBPACKAGE_PATH: Path = (
    Path(__file__).parent / "dummy_package" / "dummy_subpackage"
)
DUPLICATE_DUMMY: str = "fixit.common.tests.duplicate_dummy"
DUPLICATE_DUMMY_PATH: Path = Path(__file__).parent / "duplicate_dummy"

# Using dummy config file, test whether the rule import helpers work as expected.
class ImportsTest(UnitTest):
    def setUp(self) -> None:
        # We need to change the working directory so that the dummy config file is used.
        self.old_wd = os.getcwd()
        test_dir = DUMMY_SUBPACKAGE_PATH
        os.chdir(test_dir)

        # We also need to clear the lru_cache for the get_lint_config function between tests.
        getattr(get_lint_config, "cache_clear")()

    def tearDown(self) -> None:
        # Need to change back to original working directory so that we don't mess with other unit tests.
        os.chdir(self.old_wd)
        getattr(get_lint_config, "cache_clear")()

    def test_get_rules_from_config(self) -> None:
        rules = get_rules_from_config()

        # Assert all rules are imported as expected.
        self.assertEqual(len(rules), 3)
        expected_rules = {
            f"{DUMMY_SUBPACKAGE}.dummy",
            f"{DUMMY_PACKAGE}.dummy_1",
            f"{DUMMY_PACKAGE}.dummy_2",
        }
        self.assertEqual(expected_rules, {r.__module__ for r in rules})

    def test_get_rules_from_config_duplicate(self) -> None:
        # DUPLICATE_DUMMY_PATH points to the top-level tests package which contains two of the same rule name.
        os.chdir(DUPLICATE_DUMMY_PATH)
        with self.assertRaisesRegex(
            DuplicateLintRuleNameError, r"Lint rule name DummyRule1 is duplicated\."
        ):
            # We have two dummy lint rules with the same name. Verify this raises an error.
            get_rules_from_config()

    def test_import_rule_from_package(self) -> None:
        rules_package = get_lint_config().packages
        self.assertEqual(rules_package, [DUMMY_PACKAGE, DUMMY_SUBPACKAGE])

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

    def test_merge_lint_configs(self) -> None:
        merged_config = _merge_lint_configs()
        expected_config = {
            "fixture_dir": f"{os.getcwd()}",
            "repo_root": f"{os.getcwd()}",
            "block_list_rules": ["BlockedDummyRule1", "BlockedDummyRule2"],
            "allow_list_rules": [
                "DummyRule1",
                "DummyRule2",
                "DummyRule3",
                "BlockedDummyRule2",
            ],
            "inherit": True,
            "packages": [
                "fixit.common.tests.dummy_package",
                "fixit.common.tests.dummy_package.dummy_subpackage",
            ],
        }
        self.assertEqual(expected_config, merged_config)


class AllowListTest(UnitTest):
    def setUp(self) -> None:
        # We need to change the working directory so that the dummy config file is used.
        self.old_wd = os.getcwd()
        self.test_dir = Path(__file__).parent
        os.chdir(self.test_dir)
        self.next_dir = os.path.join(os.getcwd(), "dummy_package")
        self.sub_dir = os.path.join(self.next_dir, "dummy_subpackage")
        os.chdir(self.sub_dir)

        # We also need to clear the lru_cache for the get_lint_config function between tests.
        getattr(get_lint_config, "cache_clear")()
        shutil.copyfile(DUMMY_CONFIG_PATH, "_.fixit.config.yaml")

    def tearDown(self) -> None:
        shutil.copyfile("_.fixit.config.yaml", DUMMY_CONFIG_PATH)
        os.remove("_.fixit.config.yaml")
        # Need to change back to original working directory so that we don't mess with other unit tests.
        os.chdir(self.old_wd)
        getattr(get_lint_config, "cache_clear")()

    def test_allow_list_rules_omit_one(self) -> None:
        allow_block = dedent_with_lstrip(
            """
            allow_list_rules:
            - DummyRule4
            """
        )
        with open(DUMMY_CONFIG_PATH, "a") as f:
            f.write(allow_block)
        rules = get_rules_from_config()

        self.assertEqual(len(rules), 4)
        self.assertIn("DummyRule4", {r.__name__ for r in rules})

    def test_allow_list_rules_block_list_overrides(self) -> None:
        allow_block = dedent_with_lstrip(
            """
            allow_list_rules:
            - BlockedDummyRule1
            """
        )
        with open(DUMMY_CONFIG_PATH, "a") as f:
            f.write(allow_block)
        rules = get_rules_from_config()
        # BlockedDummyRule1 is still not included because it is in the block_rules_list
        self.assertNotIn("BlockedDummyRule1", {r.__name__ for r in rules})
        self.assertEqual(len(rules), 3)

    def test_allow_list_rules_empty_subdir(self) -> None:
        # Empty allow_list_rules at the leaf means only inherited rules are on
        allow_block = "allow_list_rules: []"
        with open(DUMMY_CONFIG_PATH, "a") as f:
            f.write(allow_block)
        rules = get_rules_from_config()
        self.assertNotIn("DummyRule4", {r.__name__ for r in rules})
        self.assertEqual(len(rules), 3)

    def test_allow_list_rules_empty_topdir(self) -> None:
        # Empty allow_list_rules means all rules are on by default
        shutil.copyfile(f"../../{DUMMY_CONFIG_PATH}", "../../_.dummy.fixit.config.yaml")

        new_config = {
            "block_list_rules": ["BlockedDummyRule1"],
            "allow_list_rules": [],
            "packages": ["fixit.common.tests.dummy_package"],
            "repo_root": ".",
            "inherit": False,  # don't accidentally grab all the rules!
        }
        with open(f"../../{DUMMY_CONFIG_PATH}", "w") as f:
            f.write(json.dumps(new_config))
        os.chdir(self.test_dir)
        top_rules = get_rules_from_config()
        os.chdir(self.sub_dir)
        getattr(get_lint_config, "cache_clear")()
        sub_rules = get_rules_from_config()
        shutil.copyfile("../../_.dummy.fixit.config.yaml", f"../../{DUMMY_CONFIG_PATH}")
        os.remove("../../_.dummy.fixit.config.yaml")
        expected_top_rules = {
            "DummyRule1",
            "DummyRule2",
            "DummyRule3",
            "DummyRule4",
            "BlockedDummyRule2",
        }
        self.assertEqual(expected_top_rules, {r.__name__ for r in top_rules})
        self.assertEqual(len(top_rules), 5)
        # A subdir can override an empty allow_list_rules and effectively turn off rules turned on in root
        expected_sub_rules = {
            "DummyRule3",
        }
        self.assertEqual(expected_sub_rules, {r.__name__ for r in sub_rules})
        self.assertEqual(len(sub_rules), 1)

    def test_allow_list_rules_missing_subdir(self) -> None:
        # Missing allow_list_rules at the leaf means only inherited rules are on
        rules = get_rules_from_config()
        # All not-blocked rules should be imported.
        expected_rules = {
            f"{DUMMY_SUBPACKAGE}.dummy",
            f"{DUMMY_PACKAGE}.dummy_1",
            f"{DUMMY_PACKAGE}.dummy_2",
        }
        self.assertEqual(expected_rules, {r.__module__ for r in rules})
        self.assertNotIn("DummyRule4", {r.__name__ for r in rules})
        self.assertEqual(len(rules), 3)

    def test_allow_list_rules_missing_topdir(self) -> None:
        # Missing allow_list_rules means all rules are on by default
        shutil.copyfile(f"../../{DUMMY_CONFIG_PATH}", "../../_.dummy.fixit.config.yaml")
        new_config = {
            "block_list_rules": ["BlockedDummyRule1"],
            "packages": ["fixit.common.tests.dummy_package"],
            "repo_root": ".",
            "inherit": False,  # don't accidentally grab all the rules!
        }
        with open(f"../../{DUMMY_CONFIG_PATH}", "w") as f:
            f.write(json.dumps(new_config))
        os.chdir(self.test_dir)
        top_rules = get_rules_from_config()
        getattr(get_lint_config, "cache_clear")()
        os.chdir(self.sub_dir)
        sub_rules = get_rules_from_config()
        shutil.copyfile("../../_.dummy.fixit.config.yaml", f"../../{DUMMY_CONFIG_PATH}")
        os.remove("../../_.dummy.fixit.config.yaml")
        expected_top_rules = {
            "DummyRule1",
            "DummyRule2",
            "DummyRule3",
            "DummyRule4",
            "BlockedDummyRule2",
        }
        self.assertEqual(expected_top_rules, {r.__name__ for r in top_rules})
        self.assertEqual(len(top_rules), 5)
        # A subdir can override an empty allow_list_rules and effectively turn off rules turned on in root
        expected_sub_rules = {
            "DummyRule3",
        }
        self.assertEqual(expected_sub_rules, {r.__name__ for r in sub_rules})
        self.assertEqual(len(sub_rules), 1)
