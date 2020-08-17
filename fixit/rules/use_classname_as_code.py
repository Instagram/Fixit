# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
from typing import Optional, cast

import libcst as cst
import libcst.matchers as m
from libcst.metadata import QualifiedName, QualifiedNameProvider, QualifiedNameSource

from fixit.common.base import CstContext, CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class UseClassNameAsCodeRule(CstLintRule):
    """
    Meta lint rule checking that codes of lint rules are migrated to new format.
    """

    MESSAGE = "`IG`-series codes are deprecated. Use class name as code instead."
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)
    VALID = [
        Valid(
            """
        MESSAGE = "This is a message"
        """
        ),
        Valid(
            """
        from fixit.common.base import CstLintRule
        class FakeRule(CstLintRule):
            MESSAGE = "This is a message"
        """
        ),
        Valid(
            """
        from fixit.common.base import CstLintRule
        class FakeRule(CstLintRule):
            INVALID = [
                Invalid(
                    code="",
                    kind="FakeRule"
                )
            ]
        """
        ),
    ]
    INVALID = [
        Invalid(
            code="""
            MESSAGE = "IG90000 Message"
            """,
            kind="UseClassNameAsCodeRule",
            expected_replacement="""
            MESSAGE = "Message"
            """,
        ),
        Invalid(
            code="""
            from fixit.common.base import CstLintRule
            class FakeRule(CstLintRule):
                INVALID = [
                    Invalid(
                        code="",
                        kind="IG000"
                    )
                ]
            """,
            kind="UseClassNameAsCodeRule",
            expected_replacement="""
            from fixit.common.base import CstLintRule
            class FakeRule(CstLintRule):
                INVALID = [
                    Invalid(
                        code="",
                        kind="FakeRule"
                    )
                ]
            """,
        ),
    ]

    QUALIFIED_CSTLINTRULE: QualifiedName = QualifiedName(
        name="fixit.common.base.CstLintRule", source=QualifiedNameSource.IMPORT
    )

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        self.lint_rule_classname: Optional[str] = None
        self.inside_invalid_call: bool = False

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        # Check if this is a LintRule class definition
        for base_class in node.bases:
            if QualifiedNameProvider.has_name(
                self, base_class.value, self.QUALIFIED_CSTLINTRULE
            ):
                self.lint_rule_classname = node.name.value
                return

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        for base_class in original_node.bases:
            if QualifiedNameProvider.has_name(
                self, base_class.value, self.QUALIFIED_CSTLINTRULE
            ):
                self.lint_rule_classname = None
                return

    def visit_SimpleString(self, node: cst.SimpleString) -> None:
        matched = re.match(r"^(\'|\")(?P<igcode>IG\d+ )\S", node.value)

        if matched:
            replacement_string = node.value.replace(matched.group("igcode"), "", 1)
            self.report(
                node,
                self.MESSAGE,
                replacement=node.with_changes(value=replacement_string),
            )

    def visit_Call(self, node: cst.Call) -> None:
        func = node.func
        if m.matches(func, m.Name()):
            func = cast(cst.Name, func)
            if func.value == "Invalid":
                self.inside_invalid_call = True

    def leave_Call(self, original_node: cst.Call) -> None:
        func = original_node.func
        if m.matches(func, m.Name()):
            func = cast(cst.Name, func)
            if func.value == "Invalid":
                self.inside_invalid_call = False

    def visit_Arg(self, node: cst.Arg) -> None:
        # Replace `code` arguments to Invalid test cases
        if self.inside_invalid_call:
            arg_value = node.value
            if m.matches(arg_value, m.SimpleString()):
                arg_value = cast(cst.SimpleString, arg_value)
                string_value = arg_value.value
                matched = re.match(r"^(\'|\")(?P<igcode>IG\d+)(\'|\")\Z", string_value)
                if matched and self.lint_rule_classname is not None:
                    new_string_value = cst.SimpleString(
                        value=f'"{self.lint_rule_classname}"'
                    )
                    self.report(
                        node,
                        self.MESSAGE,
                        replacement=node.with_changes(value=new_string_value),
                    )
