# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
from typing import cast

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
                    code=""
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
            expected_replacement="""
            from fixit.common.base import CstLintRule
            class FakeRule(CstLintRule):
                INVALID = [
                    Invalid(
                        code="",
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
        self.inside_invalid_call: bool = False

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
        # Remove `kind` arguments to Invalid test cases as they are no longer needed
        if self.inside_invalid_call:
            arg_value = node.value
            if m.matches(arg_value, m.SimpleString()):
                arg_value = cast(cst.SimpleString, arg_value)
                string_value = arg_value.value
                matched = re.match(r"^(\'|\")(?P<igcode>IG\d+)(\'|\")\Z", string_value)
                if matched:
                    self.report(
                        node, self.MESSAGE, replacement=cst.RemovalSentinel.REMOVE,
                    )