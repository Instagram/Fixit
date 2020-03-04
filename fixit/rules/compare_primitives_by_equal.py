# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class ComparePrimitivesByEqualRule(CstLintRule):
    ONCALL_SHORTNAME = "instagram_server_framework"
    MESSAGE = "IG85 Don't use `is` or `is not` to compare primitives, as they compare references. Use == or != instead."
    VALID = [
        Valid("a == 1"),
        Valid("a == '1'"),
        Valid("a != '1'"),
        Valid("'3' == '1'"),
        Valid("3 == '1'"),
        Valid("3 > 2 > 1"),
        Valid("3 > 2 > '1'"),
        Valid("a is b > 1"),
        Valid("a is b is c"),
        Valid("1 > b is c"),
    ]
    INVALID = [
        Invalid("a is 1", "IG85", expected_replacement="a == 1"),
        Invalid("a is '1'", "IG85", expected_replacement="a == '1'"),
        Invalid("a is f'1{b}'", "IG85", expected_replacement="a == f'1{b}'"),
        Invalid("a is not f'1{d}'", "IG85", expected_replacement="a != f'1{d}'"),
        Invalid("1 is a", "IG85", expected_replacement="1 == a"),
        Invalid("'2' > '1' is a", "IG85", expected_replacement="'2' > '1' == a"),
        Invalid("3 > a is 2", "IG85", expected_replacement="3 > a == 2"),
        Invalid("1  is   2", "IG85", expected_replacement="1  ==   2"),
    ]
    PRIMITIVES = (cst.BaseNumber, cst.BaseString)

    def visit_Comparison(self, node: cst.Comparison) -> None:
        prev_comparator = node.left
        for target in node.comparisons:
            op, comparator = target.operator, target.comparator
            if isinstance(op, (cst.Is, cst.IsNot)):
                if (
                    prev_comparator and isinstance(prev_comparator, self.PRIMITIVES)
                ) or isinstance(comparator, self.PRIMITIVES):
                    self.report(node, replacement=self.replace_operators(node))
                    return
            prev_comparator = comparator

    def replace_operators(self, node: cst.Comparison) -> cst.Comparison:
        prev_comparator = node.left
        comparisons = []
        for target in node.comparisons:
            op, comparator = target.operator, target.comparator
            if isinstance(op, (cst.Is, cst.IsNot)):
                if isinstance(prev_comparator, self.PRIMITIVES) or isinstance(
                    comparator, self.PRIMITIVES
                ):
                    target = target.with_changes(
                        operator=cst.Equal(
                            whitespace_before=op.whitespace_before,
                            whitespace_after=op.whitespace_after,
                        )
                        if isinstance(op, cst.Is)
                        else cst.NotEqual(
                            whitespace_before=op.whitespace_before,
                            whitespace_after=op.whitespace_after,
                        )
                    )
            comparisons.append(target)
            prev_comparator = comparator

        return node.with_changes(comparisons=comparisons)
