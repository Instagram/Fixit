# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class NoUnnecessaryFormatStringRule(CstLintRule):
    """
    Remove unnecessary f-string without placeholders.
    """

    MESSAGE: str = "f-string doesn't have placeholders, remove unnecessary f-string."

    VALID = [
        Valid('good: str = "good"'),
        Valid('good: str = f"with_arg{arg}"'),
        Valid('good = "good{arg1}".format(1234)'),
        Valid('good = "good".format()'),
        Valid('good = "good" % {}'),
        Valid('good = "good" % ()'),
        Valid('good = rf"good\t+{bar}"'),
    ]

    INVALID = [
        Invalid(
            'bad: str = f"bad" + "bad"',
            line=1,
            expected_replacement='bad: str = "bad" + "bad"',
        ),
        Invalid(
            "bad: str = f'bad'",
            line=1,
            expected_replacement="bad: str = 'bad'",
        ),
        Invalid(
            "bad: str = rf'bad\t+'",
            line=1,
            expected_replacement="bad: str = r'bad\t+'",
        ),
        Invalid(
            'bad: str = f"no args but messing up {{ braces }}"',
            line=1,
            expected_replacement='bad: str = "no args but messing up { braces }"',
        ),
    ]

    def visit_FormattedString(self, node: cst.FormattedString) -> None:
        if not m.matches(node, m.FormattedString(parts=(m.FormattedStringText(),))):
            return

        old_string_inner = cst.ensure_type(node.parts[0], cst.FormattedStringText).value
        if "{{" in old_string_inner or "}}" in old_string_inner:
            old_string_inner = old_string_inner.replace("{{", "{").replace("}}", "}")

        new_string_literal = (
            node.start.replace("f", "").replace("F", "") + old_string_inner + node.end
        )

        self.report(node, replacement=cst.SimpleString(new_string_literal))
