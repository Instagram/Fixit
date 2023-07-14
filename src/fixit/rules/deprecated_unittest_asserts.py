# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit import Invalid, LintRule, Valid


class DeprecatedUnittestAsserts(LintRule):
    """
    Discourages the use of various deprecated unittest.TestCase functions

    See https://docs.python.org/3/library/unittest.html#deprecated-aliases
    """

    MESSAGE: str = "{deprecated} is deprecated, use {replacement} instead"
    VALID = [
        # correct methods
        Valid("self.assertEqual(a, b)"),
        Valid("self.assertNotEqual(a, b)"),
        Valid("self.assertAlmostEqual(a, b)"),
        Valid("self.assertNotAlmostEqual(a, b)"),
        Valid("self.assertRegex(text, regex)"),
        Valid("self.assertNotRegex(text, regex)"),
        Valid("self.assertRaisesRegex(exception, regex)"),
        # not test methods
        Valid("obj.assertEquals(a, b)"),
        Valid("obj.assertNotEquals(a, b)"),
    ]
    INVALID = [
        Invalid(
            "self.assertEquals(a, b)",
            expected_message="assertEquals is deprecated, use assertEqual instead",
            expected_replacement="self.assertEqual(a, b)",
        ),
        Invalid(
            "self.assertNotEquals(a, b)",
            expected_message="assertNotEquals is deprecated, use assertNotEqual instead",
            expected_replacement="self.assertNotEqual(a, b)",
        ),
        Invalid(
            "self.assertAlmostEquals(a, b)",
            expected_message="assertAlmostEquals is deprecated, use assertAlmostEqual instead",
            expected_replacement="self.assertAlmostEqual(a, b)",
        ),
        Invalid(
            "self.assertNotAlmostEquals(a, b)",
            expected_message="assertNotAlmostEquals is deprecated, use assertNotAlmostEqual instead",
            expected_replacement="self.assertNotAlmostEqual(a, b)",
        ),
        Invalid(
            "self.assertRegexpMatches(text, regex)",
            expected_message="assertRegexpMatches is deprecated, use assertRegex instead",
            expected_replacement="self.assertRegex(text, regex)",
        ),
        Invalid(
            "self.assertNotRegexpMatches(text, regex)",
            expected_message="assertNotRegexpMatches is deprecated, use assertNotRegex instead",
            expected_replacement="self.assertNotRegex(text, regex)",
        ),
        Invalid(
            "self.assertRaisesRegexp(exception, regex)",
            expected_message="assertRaisesRegexp is deprecated, use assertRaisesRegex instead",
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
        for deprecated, replacement in replacements.items():
            if m.matches(
                node,
                m.Call(func=m.Attribute(value=m.Name("self"), attr=m.Name(deprecated))),
            ):
                new_call = node.with_deep_changes(
                    old_node=cst.ensure_type(node.func, cst.Attribute).attr,
                    value=replacement,
                )
                self.report(
                    node,
                    self.MESSAGE.format(deprecated=deprecated, replacement=replacement),
                    replacement=new_call,
                )
                break
