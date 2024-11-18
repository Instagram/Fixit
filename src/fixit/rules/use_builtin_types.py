# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Set

import libcst

from fixit import Invalid, LintRule, Valid
from libcst.metadata import QualifiedNameProvider, ScopeProvider


REPLACE_TYPING_TYPE_ANNOTATION: str = (
    "You are using typing.{typing_type} as a type annotation "
    + "but you should use {correct_type} instead."
)

TYPING_TYPE_TO_REPLACE: Set[str] = {"Dict", "List", "Set", "Tuple", "Type"}
QUALIFIED_TYPES_TO_REPLACE: Set[str] = {f"typing.{s}" for s in TYPING_TYPE_TO_REPLACE}


class UseBuiltinTypes(LintRule):
    """
    Enforces the use of builtin types instead of their aliases from the ``typing``
    module in Python 3.10 and later.
    """

    PYTHON_VERSION = ">= 3.10"

    METADATA_DEPENDENCIES = (
        QualifiedNameProvider,
        ScopeProvider,
    )
    VALID = [
        Valid(
            """
            def fuction(list: list[str]) -> None:
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
            from typing import List
            def whatever(list: List[str]) -> None:
                pass
            """,
            expected_replacement="""
            from typing import List
            def whatever(list: list[str]) -> None:
                pass
            """,
        ),
        Invalid(
            """
            from typing import Dict
            def func() -> None:
                thing: Dict[str, str] = {}
            """,
            expected_replacement="""
            from typing import Dict
            def func() -> None:
                thing: dict[str, str] = {}
            """,
        ),
        Invalid(
            """
            from typing import Tuple
            def func() -> None:
                thing: Tuple[str]
            """,
            expected_replacement="""
            from typing import Tuple
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

        is_typing_type = node.value in TYPING_TYPE_TO_REPLACE and all(
            qualified_name.name in QUALIFIED_TYPES_TO_REPLACE
            for qualified_name in qualified_names
        )

        if self.annotation_counter > 0 and is_typing_type:
            correct_type = node.value.title()
            scope = self.get_metadata(ScopeProvider, node)
            replacement = None
            if scope is not None and correct_type in scope:
                replacement = node.with_changes(value=correct_type)
            self.report(
                node,
                REPLACE_TYPING_TYPE_ANNOTATION.format(
                    typing_type=node.value, correct_type=correct_type
                ),
                replacement=replacement,
            )
