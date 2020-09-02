# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List

import libcst as cst

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class UsePlusForStringConcatRule(CstLintRule):
    """
    Enforces use of explicit string concatenations using a ``+`` sign where an implicit concatenation is detected.
    An implicit concatenation is a tuple or a call with multiple strings and a missing comma, e.g: ``("a" "b")``, and may have unexpected results.
    """

    MESSAGE: str = (
        "Implicit string concatenation detected, please add '+' to be explicit. "
        + 'E.g. a tuple or a call ("a" "b") with a missing comma results in multiple strings '
        + "being concatenated as one string and causes unexpected behaviour."
    )
    VALID = [Valid("'abc'"), Valid("'abc' + 'def'"), Valid("f'abc'")]
    INVALID = [
        Invalid("'ab' 'cd'", expected_replacement="('ab' + 'cd')",),
        # We can deal with nested concatenated strings
        Invalid(
            "'ab' 'cd' 'ef' 'gh'", expected_replacement="('ab' + 'cd' + 'ef' + 'gh')",
        ),
        # works for f-strings too
        Invalid("f'ab' f'cd'", expected_replacement="(f'ab' + f'cd')",),
        # arbitrary whitespace between the elements is preserved
        Invalid(
            """
                (
                    # comment
                    'ab'  # middle comment
                    'cd'  # trailing comment
                )
            """,
            expected_replacement="""
                (
                    # comment
                    'ab'  # middle comment
                    + 'cd'  # trailing comment
                )
            """,
        ),
    ]

    def visit_ConcatenatedString(self, node: cst.ConcatenatedString) -> None:
        # Skip if our immediate parent is also a ConcatenatedString, since our parent
        # should've already reported this violation.
        if isinstance(self.context.node_stack[-2], cst.ConcatenatedString):
            return

        # collect nested ConcatenatedString nodes into a flat list from outer to
        # innermost children
        children: List[cst.ConcatenatedString] = []
        el = node
        while isinstance(el, cst.ConcatenatedString):
            children.append(el)
            # left cannot be a ConcatenatedString, only right can.
            el = el.right

        # Build up a replacement by starting with the innermost child
        replacement = children[-1].right
        for el in reversed(children):
            replacement = cst.BinaryOperation(
                left=el.left,  # left is never a ConcatenatedString
                operator=cst.Add(
                    whitespace_before=el.whitespace_between,
                    whitespace_after=cst.SimpleWhitespace(" "),
                ),
                right=replacement,
                lpar=el.lpar,
                rpar=el.rpar,
            )

        # A binary operation has a lower priority in the order-of-operations than an
        # implicitly concatenated string, so we need to make sure the replacement is
        # parenthesized to make our change safe.
        if not replacement.lpar:
            # There's a good chance that the formatting might be messed up by this, but
            # black should be able to sort it out when it gets run next time.
            #
            # Because of the changes needed (e.g. increased indentation of children),
            # it's not really sane/possible for us to format this any better.
            replacement = replacement.with_changes(
                lpar=[cst.LeftParen()], rpar=[cst.RightParen()]
            )

        self.report(node, replacement=replacement)
