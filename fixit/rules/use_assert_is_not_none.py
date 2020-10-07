# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m
from libcst.helpers import ensure_type

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class UseAssertIsNotNoneRule(CstLintRule):
    """
    Discourages use of ``assertTrue(x is not None)`` as it is deprecated (https://docs.python.org/2/library/unittest.html#deprecated-aliases).
    Use ``assertIsNotNone(x)`` instead.

    """

    MESSAGE: str = (
        '"assertTrue" is deprecated. Use "assertIsNotNone" instead.\n'
        + "See https://docs.python.org/2/library/unittest.html#deprecated-aliases"
    )

    VALID = [
        Valid("self.assertTrue(x is None)"),
        Valid("self.assertTrue(not x is None)"),
        Valid("self.assertTrue(x)"),
    ]

    INVALID = [
        Invalid(
            "self.assertTrue(a is not None)",
            expected_replacement="self.assertIsNotNone(a)",
        ),
        Invalid(
            "self.assertTrue(f() is not None)",
            expected_replacement="self.assertIsNotNone(f())",
        ),
        Invalid(
            "self.assertTrue(f(x) is not None)",
            expected_replacement="self.assertIsNotNone(f(x))",
        ),
    ]

    def visit_Call(self, node: cst.Call) -> None:
        if m.matches(
            node,
            m.Call(
                func=m.Attribute(value=m.Name("self"), attr=m.Name("assertTrue")),
                args=[
                    m.Arg(
                        m.Comparison(
                            comparisons=[
                                m.ComparisonTarget(m.IsNot(), comparator=m.Name("None"))
                            ]
                        )
                    )
                ],
            ),
        ):
            arg1 = cst.Arg(ensure_type(node.args[0].value, cst.Comparison).left)

            new_call = node.with_changes(
                func=cst.Attribute(
                    value=cst.Name("self"), attr=cst.Name("assertIsNotNone")
                ),
                args=[arg1],
            )
            self.report(node, replacement=new_call)
