# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Union, cast

import libcst as cst
import libcst.matchers as m
from libcst.metadata import TypeInferenceProvider

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class UseIsNoneOnOptionalRule(CstLintRule):
    METADATA_DEPENDENCIES = (TypeInferenceProvider,)
    MESSAGE: str = (
        "IG999 When checking if an Optional has a value, avoid using it as a boolean since this calls the object's `__bool__` method. "
        + "Instead, use `is None` or `is not None`."
    )

    VALID: List[Valid] = [
        Valid(
            """
            from typing import Optional
            a: Optional[str]
            if a is not None:
                pass
            """,
        ),
        Valid(
            """
            a: bool
            if a:
                pass
            """,
        ),
    ]

    INVALID: List[Invalid] = [
        Invalid(
            code="""
            from typing import Optional

            a: Optional[str] = None
            if a:
                pass
            """,
            kind="IG999",
            expected_replacement="""
            from typing import Optional

            a: Optional[str] = None
            if a is not None:
                pass
            """,
        ),
        Invalid(
            code="""
            from typing import Optional
            a: Optional[str] = None
            x: bool = False
            if x and a:
                ...
            """,
            kind="IG999",
            expected_replacement="""
            from typing import Optional
            a: Optional[str] = None
            x: bool = False
            if x and a is not None:
                ...
            """,
        ),
        Invalid(
            code="""
            from typing import Optional
            a: Optional[str] = None
            x: bool = not a
            """,
            kind="IG999",
            expected_replacement="""
            from typing import Optional
            a: Optional[str] = None
            x: bool = a is None
            """,
        ),
        Invalid(
            code="""
            from typing import Optional
            a: Optional[str]
            x: bool
            if x or a: pass
            """,
            kind="IG999",
            expected_replacement="""
            from typing import Optional
            a: Optional[str]
            x: bool
            if x or a is not None: pass
            """,
        ),
    ]

    def visit_If(self, node: cst.If) -> None:
        test_expression: cst.BaseExpression = node.test
        if m.matches(test_expression, m.Name()):
            # We are inside a simple check such as "if x".
            test_expression = cast(cst.Name, test_expression)
            if self._is_optional_type(test_expression):
                # We want to replace "if x" with "if x is not None".
                replacement_comparison: cst.Comparison = self._gen_comparison_to_none(
                    variable_name=test_expression.value, operator=cst.IsNot()
                )
                self.report(
                    node, replacement=node.with_changes(test=replacement_comparison)
                )

    def visit_BooleanOperation(self, node: cst.BooleanOperation) -> None:
        left_expression: cst.BaseExpression = node.left
        right_expression: cst.BaseExpression = node.right
        if m.matches(node.left, m.Name()):
            # Eg: "x and y".
            left_expression = cast(cst.Name, left_expression)
            if self._is_optional_type(left_expression):
                replacement_comparison = self._gen_comparison_to_none(
                    variable_name=left_expression.value, operator=cst.IsNot()
                )
                self.report(
                    node, replacement=node.with_changes(left=replacement_comparison)
                )
        if m.matches(right_expression, m.Name()):
            # Eg: "x and y".
            right_expression = cast(cst.Name, right_expression)
            if self._is_optional_type(right_expression):
                replacement_comparison = self._gen_comparison_to_none(
                    variable_name=right_expression.value, operator=cst.IsNot()
                )
                self.report(
                    node, replacement=node.with_changes(right=replacement_comparison)
                )

    def visit_UnaryOperation(self, node: cst.UnaryOperation) -> None:
        if m.matches(node, m.UnaryOperation(operator=m.Not(), expression=m.Name())):
            # Eg: "not x".
            expression: cst.Name = cast(cst.Name, node.expression)
            if self._is_optional_type(expression):
                replacement_comparison = self._gen_comparison_to_none(
                    variable_name=expression.value, operator=cst.Is()
                )
                self.report(node, replacement=replacement_comparison)

    def _is_optional_type(self, node: cst.Name) -> bool:
        reported_type = self.get_metadata(TypeInferenceProvider, node, None)
        if reported_type is not None and reported_type.startswith("typing.Optional"):
            return True
        return False

    def _gen_comparison_to_none(
        self, variable_name: str, operator: Union[cst.Is, cst.IsNot]
    ) -> cst.Comparison:
        return cst.Comparison(
            left=cst.Name(value=variable_name),
            comparisons=[
                cst.ComparisonTarget(
                    operator=operator, comparator=cst.Name(value="None")
                )
            ],
        )
