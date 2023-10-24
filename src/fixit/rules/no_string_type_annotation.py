# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Set

import libcst as cst
import libcst.matchers as m
from libcst.metadata import QualifiedNameProvider

from fixit import CodePosition, CodeRange, Invalid, LintRule, Valid


class NoStringTypeAnnotation(LintRule):
    """
    Enforce the use of type identifier instead of using string type hints for simplicity and better syntax highlighting.
    Starting in Python 3.7, ``from __future__ import annotations`` can postpone evaluation of type annotations
    `PEP 563 <https://www.python.org/dev/peps/pep-0563/#forward-references>`_
    and thus forward references no longer need to use string annotation style.
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
        Valid(
            """
            import typing

            def foo() -> typing.Optional[typing.Literal["class", "function"]]:
                return "class"
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
            expected_replacement="""
            from __future__ import annotations

            from a.b import Class

            def foo() -> Class:
                return Class()
            """,
            range=CodeRange(start=CodePosition(5, 13), end=CodePosition(5, 20)),
        ),
        Invalid(
            """
            from __future__ import annotations

            from a.b import Class

            async def foo() -> "Class":
                return await Class()
            """,
            expected_replacement="""
            from __future__ import annotations

            from a.b import Class

            async def foo() -> Class:
                return await Class()
            """,
            range=CodeRange(start=CodePosition(5, 19), end=CodePosition(5, 26)),
        ),
        Invalid(
            """
            from __future__ import annotations

            import typing
            from a.b import Class

            def foo() -> typing.Type["Class"]:
                return Class
            """,
            expected_replacement="""
            from __future__ import annotations

            import typing
            from a.b import Class

            def foo() -> typing.Type[Class]:
                return Class
            """,
            range=CodeRange(start=CodePosition(6, 25), end=CodePosition(6, 32)),
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
            expected_replacement="""
            from __future__ import annotations

            import typing
            from a.b import Class
            from c import func

            def foo() -> Optional[typing.Type[Class]]:
                return Class if func() else None
            """,
            range=CodeRange(start=CodePosition(7, 34), end=CodePosition(7, 41)),
        ),
        Invalid(
            """
            from __future__ import annotations

            from a.b import Class

            def foo(arg: "Class") -> None:
                pass

            foo(Class())
            """,
            expected_replacement="""
            from __future__ import annotations

            from a.b import Class

            def foo(arg: Class) -> None:
                pass

            foo(Class())
            """,
            range=CodeRange(start=CodePosition(5, 13), end=CodePosition(5, 20)),
        ),
        Invalid(
            """
            from __future__ import annotations

            from a.b import Class

            module_var: "Class" = Class()
            """,
            expected_replacement="""
            from __future__ import annotations

            from a.b import Class

            module_var: Class = Class()
            """,
            range=CodeRange(start=CodePosition(5, 12), end=CodePosition(5, 19)),
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
            expected_replacement="""
            from __future__ import annotations

            import typing
            from typing_extensions import Literal
            from a.b import Class

            def foo() -> typing.Tuple[Literal["a", "b"], Class]:
                return Class()
            """,
            range=CodeRange(start=CodePosition(7, 45), end=CodePosition(7, 52)),
        ),
    ]

    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    def __init__(self) -> None:
        super().__init__()
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
                            n.name
                            in (
                                "typing.Literal",
                                "typing_extensions.Literal",
                            )
                            for n in qualnames
                        ),
                    )
                ),
                metadata_resolver=self,
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
            # This is not allowed past Python3.7 since it's no longer necessary.
            value = node.evaluated_value
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            try:
                repl = cst.parse_expression(value)
                self.report(node, replacement=repl)
            except cst.ParserSyntaxError:
                self.report(node)
