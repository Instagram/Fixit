# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Union

import libcst as cst
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
        if isinstance(test_expression, cst.Name):
            # We are inside a simple check such as "if x".
            name_node_type = self.get_metadata(TypeInferenceProvider, test_expression)
            if self.is_optional_type(name_node_type):
                # We want to replace "if x" with "if x is not None".
                replacement_comparison: cst.Comparison = self.gen_comparison_to_none(
                    variable_name=test_expression.value, operator=cst.IsNot()
                )
                self.report(
                    node, replacement=node.with_changes(test=replacement_comparison)
                )

    def visit_BooleanOperation(self, node: cst.BooleanOperation) -> None:
        # Eg: "x and y".
        left_expression: cst.BaseExpression = node.left
        right_expression: cst.BaseExpression = node.right
        if isinstance(left_expression, cst.Name):
            name_node_type = self.get_metadata(TypeInferenceProvider, left_expression)
            if self.is_optional_type(name_node_type):
                replacement_comparison = self.gen_comparison_to_none(
                    variable_name=left_expression.value, operator=cst.IsNot()
                )
                self.report(
                    node, replacement=node.with_changes(left=replacement_comparison)
                )
        if isinstance(right_expression, cst.Name):
            name_node_type = self.get_metadata(TypeInferenceProvider, right_expression)
            if self.is_optional_type(name_node_type):
                replacement_comparison = self.gen_comparison_to_none(
                    variable_name=right_expression.value, operator=cst.IsNot()
                )
                self.report(
                    node, replacement=node.with_changes(right=replacement_comparison)
                )

    def visit_UnaryOperation(self, node: cst.UnaryOperation) -> None:
        # Eg: "not x".
        expression: cst.BaseExpression = node.expression
        if isinstance(expression, cst.Name) and isinstance(node.operator, cst.Not):
            name_node_type = self.get_metadata(TypeInferenceProvider, expression)
            if self.is_optional_type(name_node_type):
                replacement_comparison = self.gen_comparison_to_none(
                    variable_name=expression.value, operator=cst.Is()
                )
                self.report(node, replacement=replacement_comparison)

    def is_optional_type(self, reported_type: str) -> bool:
        if reported_type.startswith("typing.Optional"):
            return True
        return False

    def gen_comparison_to_none(
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
