# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from libcst.testing.utils import UnitTest

from fixit.rules.import_constraints import _ImportConfig


class ImportConstraintsRuleConfigTest(UnitTest):
    def test_at_least_one_rule(self) -> None:
        # Settings must have at least one rule
        with self.assertRaisesRegex(ValueError, "at least one"):
            _ImportConfig.from_config({})

        with self.assertRaisesRegex(ValueError, "at least one"):
            _ImportConfig.from_config({"rules": []})

    def test_wildcard_rule_last(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "The last rule must be a wildcard rule"
        ):
            _ImportConfig.from_config({"rules": [["module_name", "allow"]]})

        with self.assertRaisesRegex(
            ValueError, "The last rule must be a wildcard rule"
        ):
            _ImportConfig.from_config(
                {"rules": [["*", "deny"], ["module_name", "allow"]]}
            )

        with self.assertRaisesRegex(
            ValueError, "Only the last rule can be a wildcard rule"
        ):
            _ImportConfig.from_config({"rules": [["*", "deny"], ["*", "allow"]]})

    def test_allow_or_deny(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a valid RuleAction"):
            _ImportConfig.from_config(
                {"rules": [["module_name", "wut"], ["*", "deny"]]}
            )

    def test_non_boolean(self) -> None:
        with self.assertRaisesRegex(ValueError, "value must be 'True' or 'False'"):
            _ImportConfig.from_config({"ignore_tests": "blah"})
        with self.assertRaisesRegex(ValueError, "value must be 'True' or 'False'"):
            _ImportConfig.from_config({"ignore_types": "blah"})

    def test_valid(self) -> None:
        _ImportConfig.from_config(
            {
                "rules": [["a.b.c", "allow"], ["d.e.f", "allow"], ["*", "deny"]],
                "ignore_tests": True,
                "ignore_types": False,
            }
        )
