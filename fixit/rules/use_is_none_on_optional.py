# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path
from typing import List, Union

import libcst as cst
from libcst.metadata import TypeInferenceProvider

from fixit.common.base import CstLintRule
from fixit.common.utils import (
    InvalidTypeDependentTestCase as Invalid,
    ValidTypeDependentTestCase as Valid,
    invalid_type_dependent_test_case_helper,
    valid_type_dependent_test_case_helper,
)


JSON_TYPES_FOLDER: Path = Path(
    __file__
).parent.parent / "tests" / "pyre" / "use_is_none_on_optional"


class UseIsNoneOnOptionalRule(CstLintRule):
    METADATA_DEPENDENCIES = (TypeInferenceProvider,)
    MESSAGE: str = ("IG999 Message")

    VALID: List[Valid] = [
        valid_type_dependent_test_case_helper(
            """
            from typing import Optional
            a: Optional[str]
            if a is not None:
                pass
            """,
            pyre_json_data_path=JSON_TYPES_FOLDER / "VALID_0.json",
        ),
        valid_type_dependent_test_case_helper(
            """
            a: bool
            if a:
                pass
            """,
            pyre_json_data_path=JSON_TYPES_FOLDER / "VALID_1.json",
        ),
    ]

    INVALID: List[Invalid] = [
        invalid_type_dependent_test_case_helper(
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
            pyre_json_data_path=JSON_TYPES_FOLDER / "INVALID_0.json",
        ),
        invalid_type_dependent_test_case_helper(
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
            pyre_json_data_path=JSON_TYPES_FOLDER / "INVALID_1.json",
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
            name_node_type = self.get_metadata(TypeInferenceProvider, node.right)
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
                    variable_name=expression.value, operator=cst.IsNot()
                )
                self.report(node, replacement=replacement_comparison)

    def is_optional_type(self, reported_type: str) -> bool:
        if reported_type.startswith("typing.Optional["):
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
