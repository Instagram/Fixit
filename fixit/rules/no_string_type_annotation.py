# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations

from typing import Set

import libcst as cst
import libcst.matchers as m
from libcst.metadata import QualifiedNameProvider


from fixit import (
    CstContext,
    CstLintRule,
    InvalidTestCase as Invalid,
    ValidTestCase as Valid,
)


class NoStringTypeAnnotationRule(CstLintRule):
    """
    Enforce the use of type identifier instead of using string type hints.
    """

    MESSAGE = "String type hints are no longer necessary in Python, use the type identifier directly."

    VALID = [
        # Usage of a Class for instantiation and typing.
        Valid(
            """
            from a.b import Class

            def foo() -> Class:
                return Class()
            """
        ),
        Valid(
            """
            import typing
            from a.b import Class

            def foo() -> typing.Type[Class]:
                return Class
            """
        ),
        Valid(
            """
            import typing
            from a.b import Class
            from c import func

            def foo() -> typing.Optional[typing.Type[Class]]:
                return Class if func() else None
            """
        ),
        Valid(
            """
            from a.b import Class

            def foo(arg: Class) -> None:
                pass

            foo(Class())
            """
        ),
        Valid(
            """
            from a.b import Class

            module_var: Class = Class()
            """
        ),
        Valid(
            """
            from typing import Literal

            def foo() -> Literal["a", "b"]:
                return "a"
            """
        ),
        Valid(
            """
            import typing

            def foo() -> typing.Optional[typing.Literal["a", "b"]]:
                return "a"
            """
        ),
    ]

    INVALID = [
        # Using string type hints isn't needed
        Invalid(
            """
            from __future__ import annotations

            from a.b import Class

            def foo() -> "Class":
                return Class()
            """,
            line=5,
            expected_replacement="""
            from __future__ import annotations

            from a.b import Class

            def foo() -> Class:
                return Class()
            """,
        ),
        Invalid(
            """
            from __future__ import annotations

            from a.b import Class

            async def foo() -> "Class":
                return await Class()
            """,
            line=5,
            expected_replacement="""
            from __future__ import annotations

            from a.b import Class

            async def foo() -> Class:
                return await Class()
            """,
        ),
        Invalid(
            """
            from __future__ import annotations

            import typing
            from a.b import Class

            def foo() -> typing.Type["Class"]:
                return Class
            """,
            line=6,
            expected_replacement="""
            from __future__ import annotations

            import typing
            from a.b import Class

            def foo() -> typing.Type[Class]:
                return Class
            """,
        ),
        Invalid(
            """
            from __future__ import annotations

            import typing
            from a.b import Class
            from c import func

            def foo() -> Optional[typing.Type["Class"]]:
                return Class if func() else None
            """,
            line=7,
            expected_replacement="""
            from __future__ import annotations

            import typing
            from a.b import Class
            from c import func

            def foo() -> Optional[typing.Type[Class]]:
                return Class if func() else None
            """,
        ),
        Invalid(
            """
            from __future__ import annotations

            from a.b import Class

            def foo(arg: "Class") -> None:
                pass

            foo(Class())
            """,
            line=5,
            expected_replacement="""
            from __future__ import annotations

            from a.b import Class

            def foo(arg: Class) -> None:
                pass

            foo(Class())
            """,
        ),
        Invalid(
            """
            from __future__ import annotations

            from a.b import Class

            module_var: "Class" = Class()
            """,
            line=5,
            expected_replacement="""
            from __future__ import annotations

            from a.b import Class

            module_var: Class = Class()
            """,
        ),
        Invalid(
            """
            from __future__ import annotations

            import typing
            from typing_extensions import Literal
            from a.b import Class

            def foo() -> typing.Tuple[Literal["a", "b"], "Class"]:
                return Class()
            """,
            line=7,
            expected_replacement="""
            from __future__ import annotations

            import typing
            from typing_extensions import Literal
            from a.b import Class

            def foo() -> typing.Tuple[Literal["a", "b"], Class]:
                return Class()
            """,
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        self.in_annotation: Set[cst.Annotation] = set()
        self.in_literal: Set[cst.Subscript] = set()
        self.has_future_annotations_import = False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if m.matches(
            node,
            m.ImportFrom(
                module=m.Name("__future__"),
                names=[
                    m.ZeroOrMore(),
                    m.ImportAlias(name=m.Name("annotations")),
                    m.ZeroOrMore(),
                ],
            ),
        ):
            self.has_future_annotations_import = True

    def visit_Annotation(self, node: cst.Annotation) -> None:
        self.in_annotation.add(node)

    def leave_Annotation(self, original_node: cst.Annotation) -> None:
        self.in_annotation.remove(original_node)

    def visit_Subscript(self, node: cst.Subscript) -> None:
        if not self.has_future_annotations_import:
            return
        if self.in_annotation:
            if m.matches(
                node,
                m.Subscript(
                    metadata=m.MatchMetadataIfTrue(
                        QualifiedNameProvider,
                        lambda qualnames: any(
                            n.name == "typing_extensions.Literal" for n in qualnames
                        ),
                    )
                ),
                metadata_resolver=self.context.wrapper,
            ):
                self.in_literal.add(node)

    def leave_Subscript(self, original_node: cst.Subscript) -> None:
        if not self.has_future_annotations_import:
            return
        if original_node in self.in_literal:
            self.in_literal.remove(original_node)

    def visit_SimpleString(self, node: cst.SimpleString) -> None:
        if not self.has_future_annotations_import:
            return
        if self.in_annotation and not self.in_literal:
            # This is not allowed past Python3.7 since its no longer necessary.
            self.report(
                node,
                replacement=cst.parse_expression(
                    node.evaluated_value,
                    config=self.context.wrapper.module.config_for_parsing,
                ),
            )
