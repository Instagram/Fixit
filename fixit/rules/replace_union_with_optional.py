# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit.common.base import CstContext, CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid
from fixit.common.utils import ValidTestCase as Valid


class ReplaceUnionWithOptionalRule(CstLintRule):
    ONCALL_SHORTNAME = "instagram_server_framework"
    MESSAGE: str = (
        "IG125 `Optional[T]` is preferred over `Union[T, None]` or `Union[None, T]`. "
        + "Learn more: https://docs.python.org/3/library/typing.html#typing.Optional"
    )
    METADATA_DEPENDENCIES = (cst.metadata.ScopeProvider,)
    VALID = [
        Valid(
            """
            def func() -> Optional[str]:
                pass
            """
        ),
        Valid(
            """
            def func() -> Optional[Dict]:
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
            def func() -> Union[str, None]:
                pass
            """,
            "IG125",
        ),
        Invalid(
            """
            from typing import Optional
            def func() -> Union[Dict[str, int], None]:
                pass
            """,
            "IG125",
            expected_replacement="""
            from typing import Optional
            def func() -> Optional[Dict[str, int]]:
                pass
            """,
        ),
        Invalid(
            """
            from typing import Optional
            def func() -> Union[str, None]:
                pass
            """,
            "IG125",
            expected_replacement="""
            from typing import Optional
            def func() -> Optional[str]:
                pass
            """,
        ),
        Invalid(
            """
            from typing import Optional
            def func() -> Union[Dict, None]:
                pass
            """,
            "IG125",
            expected_replacement="""
            from typing import Optional
            def func() -> Optional[Dict]:
                pass
            """,
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)

    def leave_Annotation(self, original_node: cst.Annotation) -> None:
        if self.contains_union_with_none(original_node):
            scope = self.get_metadata(cst.metadata.ScopeProvider, original_node, None)
            nones = 0
            indexes = []
            replacement = None
            if scope is not None and "Optional" in scope:
                for s in cst.ensure_type(original_node.annotation, cst.Subscript).slice:
                    if m.matches(s, m.SubscriptElement(m.Index(m.Name("None")))):
                        nones += 1
                    else:
                        indexes.append(s.slice)
                if not (nones > 1) and len(indexes) == 1:
                    replacement = original_node.with_changes(
                        annotation=cst.Subscript(
                            value=cst.Name("Optional"),
                            slice=(cst.SubscriptElement(indexes[0]),),
                        )
                    )
                    # TODO(T57106602) refactor lint replacement once extract exists
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
