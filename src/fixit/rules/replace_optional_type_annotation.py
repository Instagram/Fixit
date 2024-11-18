# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit import Invalid, LintRule, Valid


class ReplaceOptionalTypeAnnotation(LintRule):
    """
    Enforces the use of ``T | None`` over ``Optional[T]`` and ``Union[T, None]`` and ``Union[None, T]``.
    See https://docs.python.org/3/library/stdtypes.html#types-union.
    """

    MESSAGE: str = (
        "`T | None` is preferred over `Optional[T]` or `Union[T, None]` or `Union[None, T]`. "
        + "Learn more: https://docs.python.org/3/library/stdtypes.html#types-union"
    )
    VALID = [
        Valid(
            """
            def func() -> str | None:
                pass
            """
        ),
        Valid(
            """
            def func() -> Dict | None:
                pass
            """
        ),
        Valid(
            """
            def func() -> Union[str, int, None]:
                pass
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            def func() -> Optional[str]:
                pass
            """,
            expected_replacement="""
            def func() -> str | None:
                pass
            """,
        ),
        Invalid(
            """
            def func() -> Union[Dict[str, int], None]:
                pass
            """,
            expected_replacement="""
            def func() -> Dict[str, int] | None:
                pass
            """,
        ),
        Invalid(
            """
            def func() -> Union[str, None]:
                pass
            """,
            expected_replacement="""
            def func() -> str | None:
                pass
            """,
        ),
        Invalid(
            """
            def func() -> Union[Dict, None]:
                pass
            """,
            expected_replacement="""
            def func() -> Dict | None:
                pass
            """,
        ),
    ]

    def leave_Annotation(self, original_node: cst.Annotation) -> None:
        if self.contains_union_with_none(original_node):
            nones = 0
            indexes = []
            replacement = None
            for s in cst.ensure_type(original_node.annotation, cst.Subscript).slice:
                if m.matches(s, m.SubscriptElement(m.Index(m.Name("None")))):
                    nones += 1
                else:
                    indexes.append(s.slice)
            if not (nones > 1) and len(indexes) == 1:
                inner_type = cst.ensure_type(indexes[0], cst.Index).value
                replacement = original_node.with_changes(
                    annotation=cst.BinaryOperation(
                        operator=cst.BitOr(),
                        left=inner_type,
                        right=cst.Name("None"),
                    )
                )
            self.report(original_node, replacement=replacement)
        elif self.contains_optional(original_node):
            subscript_element = cst.ensure_type(
                original_node.annotation, cst.Subscript
            ).slice[0]
            inner_type = cst.ensure_type(subscript_element.slice, cst.Index).value
            replacement = original_node.with_changes(
                annotation=cst.BinaryOperation(
                    operator=cst.BitOr(), left=inner_type, right=cst.Name("None")
                )
            )
            self.report(original_node, replacement=replacement)

    def contains_union_with_none(self, node: cst.Annotation) -> bool:
        return m.matches(
            node,
            m.Annotation(
                m.Subscript(
                    value=m.Name("Union"),
                    slice=m.OneOf(
                        [
                            m.SubscriptElement(m.Index()),
                            m.SubscriptElement(m.Index(m.Name("None"))),
                        ],
                        [
                            m.SubscriptElement(m.Index(m.Name("None"))),
                            m.SubscriptElement(m.Index()),
                        ],
                    ),
                )
            ),
        )

    def contains_optional(self, node: cst.Annotation) -> bool:
        return m.matches(
            node,
            m.Annotation(
                m.Subscript(
                    value=m.Name("Optional"),
                    slice=[m.SubscriptElement(m.Index())],
                )
            ),
        )
