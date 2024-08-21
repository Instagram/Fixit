# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Set

import libcst

from fixit import Invalid, LintRule, Valid


REPLACE_TYPING_TYPE_ANNOTATION: str = (
    "Use lowercase primitive type {primitive_type}"
    + "instead of {typing_type} (See [PEP 585 – Type Hinting Generics In Standard Collections](https://peps.python.org/pep-0585/#forward-compatibility))"
)

CUSTOM_TYPES_TO_REPLACE: Set[str] = {"Dict", "List", "Set", "Tuple"}


class UsePrimitiveTypes(LintRule):
    """
    Enforces the use of primitive types instead of those in the ``typing`` module ()
    since they are available on and ahead of Python ``3.10``.
    """

    PYTHON_VERSION = ">= 3.10"

    VALID = [
        Valid(
            """
            def foo() -> list:
                pass
            """,
        ),
        Valid(
            """
            def bar(x: set) -> None:
                pass
            """,
        ),
        Valid(
            """
            def baz(y: tuple) -> None:
                pass
            """,
        ),
        Valid(
            """
            def qux(z: dict) -> None:
                pass
            """,
        ),
    ]

    INVALID = [
        Invalid(
            """
            def foo() -> List[int]:
                pass
            """,
            expected_replacement="""
            def foo() -> list[int]:
                pass
            """,
        ),
        Invalid(
            """
            def bar(x: Set[str]) -> None:
                pass
            """,
            expected_replacement="""
            def bar(x: set[str]) -> None:
                pass
            """,
        ),
        Invalid(
            """
            def baz(y: Tuple[int, str]) -> None:
                pass
            """,
            expected_replacement="""
            def baz(y: tuple[int, str]) -> None:
                pass
            """,
        ),
        Invalid(
            """
            def qux(z: Dict[str, int]) -> None:
                pass
            """,
            expected_replacement="""
            def qux(z: dict[str, int]) -> None:
                pass
            """,
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.annotation_counter: int = 0

    def visit_Annotation(self, node: libcst.Annotation) -> None:
        self.annotation_counter += 1

    def leave_Annotation(self, original_node: libcst.Annotation) -> None:
        self.annotation_counter -= 1

    def visit_FunctionDef(self, node: libcst.FunctionDef) -> None:
        # Check return type
        if isinstance(node.returns, libcst.Annotation):
            if isinstance(node.returns.annotation, libcst.Subscript):
                base_type = node.returns.annotation.value
                if (
                    isinstance(base_type, libcst.Name)
                    and base_type.value in CUSTOM_TYPES_TO_REPLACE
                ):
                    new_base_type = base_type.with_changes(
                        value=base_type.value.lower()
                    )
                    new_annotation = node.returns.annotation.with_changes(
                        value=new_base_type
                    )
                    new_returns = node.returns.with_changes(annotation=new_annotation)
                    new_node = node.with_changes(returns=new_returns)
                    self.report(
                        node,
                        REPLACE_TYPING_TYPE_ANNOTATION.format(
                            primitive_type=base_type.value.lower(),
                            typing_type=base_type.value,
                        ),
                        replacement=new_node,
                    )

        # Check parameter types
        for param in node.params.params:
            if isinstance(param.annotation, libcst.Annotation):
                if isinstance(param.annotation.annotation, libcst.Subscript):
                    base_type = param.annotation.annotation.value
                    if (
                        isinstance(base_type, libcst.Name)
                        and base_type.value in CUSTOM_TYPES_TO_REPLACE
                    ):
                        new_base_type = base_type.with_changes(
                            value=base_type.value.lower()
                        )
                        new_annotation = param.annotation.annotation.with_changes(
                            value=new_base_type
                        )
                        new_param_annotation = param.annotation.with_changes(
                            annotation=new_annotation
                        )
                        new_param = param.with_changes(annotation=new_param_annotation)
                        self.report(
                            param,
                            REPLACE_TYPING_TYPE_ANNOTATION.format(
                                primitive_type=base_type.value.lower(),
                                typing_type=base_type.value,
                            ),
                            replacement=new_param,
                        )
