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
    Discourages use of ``assertTrue(x is not None)`` and ``assertFalse(x is not None)`` as it is deprecated (https://docs.python.org/3.8/library/unittest.html#deprecated-aliases).
    Use ``assertIsNotNone(x)`` and ``assertIsNone(x)``) instead.

    """

    MESSAGE: str = (
        '"assertTrue" and "assertFalse" are deprecated. Use "assertIsNotNone" and "assertIsNone" instead.\n'
        + "See https://docs.python.org/3.8/library/unittest.html#deprecated-aliases"
    )

    VALID = [
        Valid("self.assertTrue(not x is None)"),
        Valid("self.assertTrue(x)"),
        Valid("self.assertFalse(not x is None)"),
        Valid("self.assertFalse(x)"),
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
        Invalid(
            "self.assertTrue(x is None)", expected_replacement="self.assertIsNone(x)"
        ),
        Invalid(
            "self.assertFalse(x is not None)",
            expected_replacement="self.assertIsNone(x)",
        ),
        Invalid(
            "self.assertFalse(f() is not None)",
            expected_replacement="self.assertIsNone(f())",
        ),
        Invalid(
            "self.assertFalse(f(x) is not None)",
            expected_replacement="self.assertIsNone(f(x))",
        ),
    ]

    def visit_Call(self, node: cst.Call) -> None:
        found_match: bool = False
        new_cst_attr: Optional[str] = None
        new_node_arg: Optional[cst.Arg] = None

        # `self.assertTrue(x is not None)` -> `self.assertIsNotNone(x)`
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
            found_match = True
            new_node_arg = cst.Arg(ensure_type(node.args[0].value, cst.Comparison).left)
            new_cst_attr = "assertIsNotNone"
        # `self.assertFalse(x is None)` -> `self.assertIsNotNone(x)`
        elif m.matches(
            node,
            m.Call(
                func=m.Attribute(value=m.Name("self"), attr=m.Name("assertFalse")),
                args=[
                    m.Arg(
                        m.Comparison(
                            comparisons=[
                                m.ComparisonTarget(m.Is(), comparator=m.Name("None"))
                            ]
                        )
                    )
                ],
            ),
        ):
            found_match = True
            new_node_arg = cst.Arg(ensure_type(node.args[0].value, cst.Comparison).left)
            new_cst_attr = "assertIsNotNone"
        # `self.assertTrue(x is None)` -> `self.assertIsNotNone(x))
        elif m.matches(
            node,
            m.Call(
                func=m.Attribute(value=m.Name("self"), attr=m.Name("assertTrue")),
                args=[
                    m.Arg(
                        m.Comparison(
                            comparisons=[
                                m.ComparisonTarget(m.Is(), comparator=m.Name("None"))
                            ]
                        )
                    )
                ],
            ),
        ):
            found_match = True
            new_node_arg = cst.Arg(ensure_type(node.args[0].value, cst.Comparison).left)
            new_cst_attr = "assertIsNone"

        # `self.assertFalse(x is not None)` -> `self.assertIsNone(x)`
        elif m.matches(
            node,
            m.Call(
                func=m.Attribute(value=m.Name("self"), attr=m.Name("assertFalse")),
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
            found_match = True
            new_node_arg = cst.Arg(ensure_type(node.args[0].value, cst.Comparison).left)
            new_cst_attr = "assertIsNone"

        if found_match:
            new_call = node.with_changes(
                func=cst.Attribute(value=cst.Name("self"), attr=cst.Name(new_cst_attr)),
                args=[new_node_arg],
            )
            self.report(node, replacement=new_call)
