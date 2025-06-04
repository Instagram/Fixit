# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m
from libcst.metadata import QualifiedName, QualifiedNameProvider, QualifiedNameSource

from fixit import Invalid, LintRule, Valid


class VariadicCallableSyntax(LintRule):
    """
    Callable types with arbitrary parameters should be written as `Callable[..., T]`
    """

    METADATA_DEPENDENCIES = (QualifiedNameProvider,)
    VALID = [
        Valid(
            """
            from typing import Callable
            x: Callable[[int], int]
            """
        ),
        Valid(
            """
            from typing import Callable
            x: Callable[[int, int, ...], int]
            """
        ),
        Valid(
            """
            from typing import Callable
            x: Callable
            """
        ),
        Valid(
            """
            from typing import Callable as C
            x: C[..., int] = ...
            """
        ),
        Valid(
            """
            from typing import Callable
            def foo(bar: Optional[Callable[..., int]]) -> Callable[..., int]:
                ...
            """
        ),
        Valid(
            """
            import typing as t
            x: t.Callable[..., int] = ...
            """
        ),
        Valid(
            """
            from typing import Callable
            x: Callable[..., int] = ...
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            from typing import Callable
            x: Callable[[...], int] = ...
            """,
            expected_replacement="""
            from typing import Callable
            x: Callable[..., int] = ...
            """,
        ),
        Invalid(
            """
            import typing as t
            x: t.Callable[[...], int] = ...
            """,
            expected_replacement="""
            import typing as t
            x: t.Callable[..., int] = ...
            """,
        ),
        Invalid(
            """
            from typing import Callable as C
            x: C[[...], int] = ...
            """,
            expected_replacement="""
            from typing import Callable as C
            x: C[..., int] = ...
            """,
        ),
        Invalid(
            """
            from typing import Callable
            def foo(bar: Optional[Callable[[...], int]]) -> Callable[[...], int]:
                ...
            """,
            expected_replacement="""
            from typing import Callable
            def foo(bar: Optional[Callable[..., int]]) -> Callable[..., int]:
                ...
            """,
        ),
    ]

    def visit_Subscript(self, node: cst.Subscript) -> None:
        if not QualifiedNameProvider.has_name(
            self,
            node,
            QualifiedName(name="typing.Callable", source=QualifiedNameSource.IMPORT),
        ):
            return
        if len(node.slice) == 2 and m.matches(
            node.slice[0],
            m.SubscriptElement(
                slice=m.Index(value=m.List(elements=[m.Element(m.Ellipsis())]))
            ),
        ):
            slices = list(node.slice)
            slices[0] = cst.SubscriptElement(cst.Index(cst.Ellipsis()))
            new_node = node.with_changes(slice=slices)
            self.report(
                node,
                self.__doc__,
                replacement=node.deep_replace(node, new_node),
            )
