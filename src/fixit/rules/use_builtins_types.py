# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Set

import libcst
from libcst.metadata import QualifiedNameProvider

from fixit import Invalid, LintRule, Valid

REPLACE_TYPING_TYPE_ANNOTATION: str = (
    "You are using typing.{typing_type} as a type annotation "
    + "but you should use builtins.{builtin_type} instead."
)

TYPING_TO_BUILTINS: Set[str] = {"List", "Dict", "Set", "Tuple"}
QUALIFIED_TYPING_TO_BUILTINS: Set[str] = {f"typing.{s}" for s in TYPING_TO_BUILTINS}

class UseBuiltInsTypes(LintRule):
    """
    Enforces the use of built-in types in type annotations in place
    of `typing.{typing_type}` for simplicity and consistency.
    """

    PYTHON_VERSION = ">= 3.10"

    METADATA_DEPENDENCIES = (
        QualifiedNameProvider,
    )

    VALID = [
        Valid(
            """
            def function(list: list[str]) -> None:
                pass
            """
        ),
        Valid(
            """
            def function() -> None:
                thing: dict[str, str] = {}
            """
        ),
        Valid(
            """
            def function() -> None:
                thing: tuple[str]
            """
        ),
    ]

    INVALID = [
        Invalid(
            """
            def function(list: List[str]) -> None:
                pass
            """,
            expected_replacement="""
            def function(list: list[str]) -> None:
                pass
            """,
        ),
        Invalid(
            """
            def func() -> None:
                thing: Dict[str, str] = {}
            """,
            expected_replacement="""
            def func() -> None:
                thing: dict[str, str] = {}
            """,
        ),
        Invalid(
            """
            def function(list: list[str]) -> List[str]:
                pass
            """,
            expected_replacement="""
            def function(list: list[str]) -> list[str]:
                pass
            """,
        ),
        Invalid(
            """
            def func() -> None:
                thing: Tuple[str]
            """,
            expected_replacement="""
            def func() -> None:
                thing: tuple[str]
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

    def visit_Name(self, node: libcst.Name) -> None:
        qualified_names = self.get_metadata(QualifiedNameProvider, node, set())

        is_typing_type = node.value in TYPING_TO_BUILTINS and all(
            qualified_name.name in QUALIFIED_TYPING_TO_BUILTINS
            for qualified_name in qualified_names
        )

        if self.annotation_counter > 0 and is_typing_type:
            builtin_type = node.value.lower()
            self.report(
                node,
                REPLACE_TYPING_TYPE_ANNOTATION.format(
                    typing_type=node.value, builtin_type=builtin_type
                ),
                replacement=node.with_changes(value=builtin_type),
            )
