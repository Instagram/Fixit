# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Dict, List, Optional, Union, cast

import libcst as cst
import libcst.matchers as m
from libcst.metadata import TypeInferenceProvider

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid
from fixit.common.report import CstLintRuleReport


class UseIsNoneOnOptionalRule(CstLintRule):
    """
    Enforces explicit use of ``is None`` or ``is not None`` when checking whether an Optional has a value.
    Directly testing an object (e.g. ``if x``) implicitely tests for a truth value which returns ``True`` unless the
    object's ``__bool__()`` method returns False, its ``__len__()`` method returns '0', or it is one of the constants ``None`` or ``False``.
    (https://docs.python.org/3.8/library/stdtypes.html#truth-value-testing).
    """

    METADATA_DEPENDENCIES = (TypeInferenceProvider,)
    MESSAGE: str = (
        "When checking if an `Optional` has a value, avoid using it as a boolean since it implicitly checks the object's `__bool__()`, `__len__()` is not `0`, or the value is not `None`. "
        + "Instead, use `is None` or `is not None` to be explicit."
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
            x: bool = False
            if a and x:
                ...
            """,
            expected_replacement="""
            from typing import Optional
            a: Optional[str] = None
            x: bool = False
            if a is not None and x:
                ...
            """,
        ),
        Invalid(
            code="""
            from typing import Optional
            a: Optional[str] = None
            x: bool = not a
            """,
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
            expected_replacement="""
            from typing import Optional
            a: Optional[str]
            x: bool
            if x or a is not None: pass
            """,
        ),
        Invalid(
            code="""
            from typing import Optional
            a: Optional[str]
            x: bool
            if x: pass
            elif a: pass
            """,
            expected_replacement="""
            from typing import Optional
            a: Optional[str]
            x: bool
            if x: pass
            elif a is not None: pass
            """,
        ),
        Invalid(
            code="""
            from typing import Optional
            a: Optional[str] = None
            b: Optional[str] = None
            if a: pass
            elif b: pass
            """,
            expected_replacement="""
            from typing import Optional
            a: Optional[str] = None
            b: Optional[str] = None
            if a is not None: pass
            elif b is not None: pass
            """,
        ),
    ]

    def leave_If(self, original_node: cst.If) -> None:
        changes: Dict[str, cst.CSTNode] = {}
        test_expression: cst.BaseExpression = original_node.test
        if m.matches(test_expression, m.Name()):
            # We are inside a simple check such as "if x".
            test_expression = cast(cst.Name, test_expression)
            if self._is_optional_type(test_expression):
                # We want to replace "if x" with "if x is not None".
                replacement_comparison: cst.Comparison = self._gen_comparison_to_none(
                    variable_name=test_expression.value, operator=cst.IsNot()
                )
                changes["test"] = replacement_comparison

        orelse = original_node.orelse
        if orelse is not None and m.matches(orelse, m.If()):
            # We want to catch this case upon leaving an `If` node so that we generate an `elif` statement correctly.
            # We check if the orelse node was reported, and if so, remove the report and generate a new report on
            # the current parent `If` node.
            new_reports = []
            orelse_report: Optional[CstLintRuleReport] = None
            for report in self.context.reports:
                if isinstance(report, CstLintRuleReport):
                    # Check whether the lint rule code matches this lint rule's code so we don't remove another
                    # lint rule's report.
                    if report.node is orelse and report.code == self.__class__.__name__:
                        orelse_report = report
                    else:
                        new_reports.append(report)
                else:
                    new_reports.append(report)
            if orelse_report is not None:
                self.context.reports = new_reports
                replacement_orelse = orelse_report.replacement_node
                changes["orelse"] = cst.ensure_type(replacement_orelse, cst.CSTNode)

        if changes:
            self.report(
                original_node, replacement=original_node.with_changes(**changes)
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
        # We want to use `startswith()` here since the type data will take on the form 'typing.Optional[SomeType]'.
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
