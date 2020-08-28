# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from libcst.testing.utils import UnitTest

from fixit.common.unused_suppressions import RemoveUnusedSuppressionsRule


class RemoveUnusedSuppressionsRuleTest(UnitTest):
    def test_used_suppression_one_code_not_removed (self) -> None:
        # One-liner comment

        # Multiliner
        pass

    def test_used_suppression_multiple_codes_not_removed (self) -> None:
        # One-liner comment

        # Multiliner
        pass

    def test_unused_suppression_one_code_removed (self) -> None:
        # One-liner comment

        # Multiliner
        pass

    def test_only_unused_codes_in_suppression_removed (self) -> None:
        # One-liner comment

        # Multiliner
        pass

    def test_suppression_not_removed_when_rule_not_run (self) -> None:
        # One-liner comment

        # Multiliner
        pass
