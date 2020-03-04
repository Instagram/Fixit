# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Optional

import libcst as cst
import libcst.matchers as m

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class NoStaticIfConditionRule(CstLintRule):
    ONCALL_SHORTNAME = "ig_creation_backend"
    MESSAGE: str = (
        "IG104 Your if condition appears to evalute to a static value (eg `or True`, `and False`). "
        + "Please double check this logic and if it is actually temporary debug code."
    )
    VALID = [
        Valid(
            """
            if my_func() or not else_func():
                pass
            """
        ),
        Valid(
            """
            if function_call(True):
                pass
            """
        ),
        Valid(
            """
            # ew who would this???
            def true():
                return False
            if true() and else_call():  # True or False
                pass
            """
        ),
        Valid(
            """
            # ew who would this???
            if False or some_func():
                pass
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            if True:
                do_something()
            """,
            "IG104",
        ),
        Invalid(
            """
            if crazy_expression or True:
                do_something()
            """,
            "IG104",
        ),
        Invalid(
            """
            if crazy_expression and False:
                do_something()
            """,
            "IG104",
        ),
        Invalid(
            """
            if crazy_expression and not True:
                do_something()
            """,
            "IG104",
        ),
        Invalid(
            """
            if crazy_expression or not False:
                do_something()
            """,
            "IG104",
        ),
        Invalid(
            """
            if crazy_expression or (something() or True):
                do_something()
            """,
            "IG104",
        ),
        Invalid(
            """
            if crazy_expression and (something() and (not True)):
                do_something()
            """,
            "IG104",
        ),
        Invalid(
            """
            if crazy_expression and (something() and (other_func() and not True)):
                do_something()
            """,
            "IG104",
        ),
        Invalid(
            """
            if (crazy_expression and (something() and (not True))) or True:
                do_something()
            """,
            "IG104",
        ),
        Invalid(
            """
            async def some_func() -> none:
                if (await expression()) and False:
                    pass
            """,
            "IG104",
        ),
    ]

    @classmethod
    def _extract_static_bool(cls, node: cst.BaseExpression) -> Optional[bool]:
        if m.matches(node, m.Call()):
            # cannot reason about function calls
            return None
        if m.matches(node, m.UnaryOperation(operator=m.Not())):
            sub_value = cls._extract_static_bool(
                cst.ensure_type(node, cst.UnaryOperation).expression
            )
            if sub_value is None:
                return None
            return not sub_value

        if m.matches(node, m.Name("True")):
            return True

        if m.matches(node, m.Name("False")):
            return False

        if m.matches(node, m.BooleanOperation()):
            node = cst.ensure_type(node, cst.BooleanOperation)
            left_value = cls._extract_static_bool(node.left)
            right_value = cls._extract_static_bool(node.right)
            if m.matches(node.operator, m.Or()):
                if right_value is True or left_value is True:
                    return True

            if m.matches(node.operator, m.And()):
                if right_value is False or left_value is False:
                    return False

        return None

    def visit_If(self, node: cst.If) -> None:
        if self._extract_static_bool(node.test) in {True, False}:
            self.report(node)
