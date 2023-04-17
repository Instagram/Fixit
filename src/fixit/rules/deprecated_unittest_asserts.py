# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class DeprecatedUnittestAssertsRule(CstLintRule):
    """
    Discourages the use of various deprecated unittest.TestCase functions - https://docs.python.org/3/library/unittest.html#deprecated-aliases
    """

    MESSAGE: str = (
        '"You are using a deprecated TestCase method.\n'
        + "See https://docs.python.org/3/library/unittest.html#deprecated-aliases and https://bugs.python.org/issue9424."
    )
    VALID = [
        Valid("self.assertEqual(a, b)"),
        Valid("self.assertNotEqual(a, b)"),
        Valid("self.assertAlmostEqual(a, b)"),
        Valid("self.assertNotAlmostEqual(a, b)"),
        Valid("self.assertRegex(text, regex)"),
        Valid("self.assertNotRegex(text, regex)"),
        Valid("self.assertRaisesRegex(exception, regex)"),
    ]
    INVALID = [
        Invalid(
            "self.assertEquals(a, b)",
            expected_replacement="self.assertEqual(a, b)",
        ),
        Invalid(
            "self.assertNotEquals(a, b)",
            expected_replacement="self.assertNotEqual(a, b)",
        ),
        Invalid(
            "self.assertAlmostEquals(a, b)",
            expected_replacement="self.assertAlmostEqual(a, b)",
        ),
        Invalid(
            "self.assertNotAlmostEquals(a, b)",
            expected_replacement="self.assertNotAlmostEqual(a, b)",
        ),
        Invalid(
            "self.assertRegexpMatches(text, regex)",
            expected_replacement="self.assertRegex(text, regex)",
        ),
        Invalid(
            "self.assertNotRegexpMatches(text, regex)",
            expected_replacement="self.assertNotRegex(text, regex)",
        ),
        Invalid(
            "self.assertRaisesRegexp(exception, regex)",
            expected_replacement="self.assertRaisesRegex(exception, regex)",
        ),
    ]

    def visit_Call(self, node: cst.Call) -> None:
        replacements = {
            "assertEquals": "assertEqual",
            "assertNotEquals": "assertNotEqual",
            "assertAlmostEquals": "assertAlmostEqual",
            "assertNotAlmostEquals": "assertNotAlmostEqual",
            "assertRegexpMatches": "assertRegex",
            "assertNotRegexpMatches": "assertNotRegex",
            "assertRaisesRegexp": "assertRaisesRegex",
        }
        for bad, replacement in replacements.items():
            if m.matches(
                node,
                m.Call(func=m.Attribute(value=m.Name("self"), attr=m.Name(bad))),
            ):
                new_call = node.with_deep_changes(
                    old_node=cst.ensure_type(node.func, cst.Attribute).attr,
                    value=replacement,
                )
                self.report(node, replacement=new_call)
                break
