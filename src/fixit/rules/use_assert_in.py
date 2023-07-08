# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m
from libcst.helpers import ensure_type

from fixit import Invalid, LintRule, Valid


class UseAssertInRule(LintRule):
    """
    Discourages use of ``assertTrue(x in y)`` and ``assertFalse(x in y)``
    as it is deprecated (https://docs.python.org/3.8/library/unittest.html#deprecated-aliases).
    Use ``assertIn(x, y)`` and ``assertNotIn(x, y)``) instead.
    """

    MESSAGE: str = (
        "Use assertIn/assertNotIn instead of assertTrue/assertFalse for inclusion check.\n"
        + "See https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertIn)"
    )

    VALID = [
        Valid("self.assertIn(a, b)"),
        Valid("self.assertIn(f(), b)"),
        Valid("self.assertIn(f(x), b)"),
        Valid("self.assertIn(f(g(x)), b)"),
        Valid("self.assertNotIn(a, b)"),
        Valid("self.assertNotIn(f(), b)"),
        Valid("self.assertNotIn(f(x), b)"),
        Valid("self.assertNotIn(f(g(x)), b)"),
    ]

    INVALID = [
        Invalid(
            "self.assertTrue(a in b)",
            expected_replacement="self.assertIn(a, b)",
        ),
        Invalid(
            "self.assertTrue(f() in b)",
            expected_replacement="self.assertIn(f(), b)",
        ),
        Invalid(
            "self.assertTrue(f(x) in b)",
            expected_replacement="self.assertIn(f(x), b)",
        ),
        Invalid(
            "self.assertTrue(f(g(x)) in b)",
            expected_replacement="self.assertIn(f(g(x)), b)",
        ),
        Invalid(
            "self.assertTrue(a not in b)",
            expected_replacement="self.assertNotIn(a, b)",
        ),
        Invalid(
            "self.assertTrue(not a in b)",
            expected_replacement="self.assertNotIn(a, b)",
        ),
        Invalid(
            "self.assertFalse(a in b)",
            expected_replacement="self.assertNotIn(a, b)",
        ),
    ]

    def visit_Call(self, node: cst.Call) -> None:
        # Todo: Make use of single extract instead of having several
        # if else statemenets to make the code more robust and readable.
        if m.matches(
            node,
            m.Call(
                func=m.Attribute(value=m.Name("self"), attr=m.Name("assertTrue")),
                args=[
                    m.Arg(
                        m.Comparison(comparisons=[m.ComparisonTarget(operator=m.In())])
                    )
                ],
            ),
        ):
            # self.assertTrue(a in b) -> self.assertIn(a, b)
            new_call = node.with_changes(
                func=cst.Attribute(value=cst.Name("self"), attr=cst.Name("assertIn")),
                args=[
                    cst.Arg(ensure_type(node.args[0].value, cst.Comparison).left),
                    cst.Arg(
                        ensure_type(node.args[0].value, cst.Comparison)
                        .comparisons[0]
                        .comparator
                    ),
                ],
            )
            self.report(node, replacement=new_call)
        else:
            # ... -> self.assertNotIn(a, b)
            matched, arg1, arg2 = False, None, None
            if m.matches(
                node,
                m.Call(
                    func=m.Attribute(value=m.Name("self"), attr=m.Name("assertTrue")),
                    args=[
                        m.Arg(
                            m.UnaryOperation(
                                operator=m.Not(),
                                expression=m.Comparison(
                                    comparisons=[m.ComparisonTarget(operator=m.In())]
                                ),
                            )
                        )
                    ],
                ),
            ):
                # self.assertTrue(not a in b) -> self.assertNotIn(a, b)
                matched = True
                arg1 = cst.Arg(
                    ensure_type(
                        ensure_type(node.args[0].value, cst.UnaryOperation).expression,
                        cst.Comparison,
                    ).left
                )
                arg2 = cst.Arg(
                    ensure_type(
                        ensure_type(node.args[0].value, cst.UnaryOperation).expression,
                        cst.Comparison,
                    )
                    .comparisons[0]
                    .comparator
                )
            elif m.matches(
                node,
                m.Call(
                    func=m.Attribute(value=m.Name("self"), attr=m.Name("assertTrue")),
                    args=[
                        m.Arg(m.Comparison(comparisons=[m.ComparisonTarget(m.NotIn())]))
                    ],
                ),
            ):
                # self.assertTrue(a not in b) -> self.assertNotIn(a, b)
                matched = True
                arg1 = cst.Arg(ensure_type(node.args[0].value, cst.Comparison).left)
                arg2 = cst.Arg(
                    ensure_type(node.args[0].value, cst.Comparison)
                    .comparisons[0]
                    .comparator
                )
            elif m.matches(
                node,
                m.Call(
                    func=m.Attribute(value=m.Name("self"), attr=m.Name("assertFalse")),
                    args=[
                        m.Arg(m.Comparison(comparisons=[m.ComparisonTarget(m.In())]))
                    ],
                ),
            ):
                # self.assertFalse(a in b) -> self.assertNotIn(a, b)
                matched = True
                arg1 = cst.Arg(ensure_type(node.args[0].value, cst.Comparison).left)
                arg2 = cst.Arg(
                    ensure_type(node.args[0].value, cst.Comparison)
                    .comparisons[0]
                    .comparator
                )

            if matched:
                new_call = node.with_changes(
                    func=cst.Attribute(
                        value=cst.Name("self"), attr=cst.Name("assertNotIn")
                    ),
                    args=[arg1, arg2],
                )
                self.report(node, replacement=new_call)
