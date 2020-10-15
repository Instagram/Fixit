# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Sequence

import libcst as cst
import libcst.matchers as m
from libcst.helpers import ensure_type

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class UseAssertIsNotNoneRule(CstLintRule):
    """
    Discourages use of ``assertTrue(x is not None)`` and ``assertFalse(x is not None)`` as it is deprecated (https://docs.python.org/3.8/library/unittest.html#deprecated-aliases).
    Use ``assertIsNotNone(x)`` and ``assertIsNone(x)``) instead.

    """

    MESSAGE: str = (
        '"assertTrue" and "assertFalse" are deprecated. Use "assertIsNotNone" and "assertIsNone" instead.\n'
        + "See https://docs.python.org/3.8/library/unittest.html#deprecated-aliases"
    )

    VALID = [
        Valid("self.assertIsNotNone(x)"),
        Valid("self.assertIsNone(x)"),
        Valid("self.assertIsNone(None)"),
        Valid("self.assertIsNotNone(f(x))"),
        Valid("self.assertIsNone(f(x))"),
        Valid("self.assertIsNone(object.key)"),
        Valid("self.assertIsNotNone(object.key)"),
    ]

    INVALID = [
        Invalid(
            "self.assertTrue(a is not None)",
            expected_replacement="self.assertIsNotNone(a)",
        ),
        Invalid(
            "self.assertTrue(not x is None)",
            expected_replacement="self.assertIsNotNone(x)",
        ),
        Invalid(
            "self.assertTrue(f() is not None)",
            expected_replacement="self.assertIsNotNone(f())",
        ),
        Invalid(
            "self.assertTrue(not x is not None)",
            expected_replacement="self.assertIsNone(x)",
        ),
        Invalid(
            "self.assertTrue(f(x) is not None)",
            expected_replacement="self.assertIsNotNone(f(x))",
        ),
        Invalid(
            "self.assertTrue(x is None)", expected_replacement="self.assertIsNone(x)"
        ),
        Invalid(
            "self.assertFalse(x is not None)",
            expected_replacement="self.assertIsNone(x)",
        ),
        Invalid(
            "self.assertFalse(not x is None)",
            expected_replacement="self.assertIsNone(x)",
        ),
        Invalid(
            "self.assertFalse(f() is not None)",
            expected_replacement="self.assertIsNone(f())",
        ),
        Invalid(
            "self.assertFalse(not x is not None)",
            expected_replacement="self.assertIsNotNone(x)",
        ),
        Invalid(
            "self.assertFalse(f(x) is not None)",
            expected_replacement="self.assertIsNone(f(x))",
        ),
        Invalid(
            "self.assertFalse(x is None)",
            expected_replacement="self.assertIsNotNone(x)",
        ),
    ]

    def visit_Call(self, node: cst.Call) -> None:
        match_compare_is_none = m.ComparisonTarget(
            m.SaveMatchedNode(
                m.OneOf(m.Is(), m.IsNot()),
                "comparison_type",
            ),
            comparator=m.Name("None"),
        )
        result = m.extract(
            node,
            m.Call(
                func=m.Attribute(
                    value=m.Name("self"),
                    attr=m.SaveMatchedNode(
                        m.OneOf(m.Name("assertTrue"), m.Name("assertFalse")),
                        "assertion_name",
                    ),
                ),
                args=[
                    m.Arg(
                        m.SaveMatchedNode(
                            m.OneOf(
                                m.Comparison(comparisons=[match_compare_is_none]),
                                m.UnaryOperation(
                                    operator=m.Not(),
                                    expression=m.Comparison(
                                        comparisons=[match_compare_is_none]
                                    ),
                                ),
                            ),
                            "argument",
                        )
                    )
                ],
            ),
        )

        if result:
            assertion_name = result["assertion_name"]
            if isinstance(assertion_name, Sequence):
                assertion_name = assertion_name[0]

            argument = result["argument"]
            if isinstance(argument, Sequence):
                argument = argument[0]

            comparison_type = result["comparison_type"]
            if isinstance(comparison_type, Sequence):
                comparison_type = comparison_type[0]

            if m.matches(argument, m.Comparison()):
                assertion_argument = ensure_type(argument, cst.Comparison).left
            else:
                assertion_argument = ensure_type(
                    ensure_type(argument, cst.UnaryOperation).expression, cst.Comparison
                ).left

            negations_seen = 0
            if m.matches(assertion_name, m.Name("assertFalse")):
                negations_seen += 1
            if m.matches(argument, m.UnaryOperation()):
                negations_seen += 1
            if m.matches(comparison_type, m.IsNot()):
                negations_seen += 1

            new_attr = "assertIsNone" if negations_seen % 2 == 0 else "assertIsNotNone"
            new_call = node.with_changes(
                func=cst.Attribute(value=cst.Name("self"), attr=cst.Name(new_attr)),
                args=[cst.Arg(assertion_argument)],
            )

            if new_call is not node:
                self.report(node, replacement=new_call)
