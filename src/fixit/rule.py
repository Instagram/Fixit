# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations

import functools
from dataclasses import replace
from typing import ClassVar, Collection, List, Mapping, Optional, Set, Union

from libcst import BatchableCSTVisitor, CSTNode
from libcst.metadata import CodePosition, CodeRange, PositionProvider, ProviderT

from .ftypes import (
    InvalidTestCase,
    LintViolation,
    NodeReplacement,
    ValidTestCase,
    VisitHook,
    VisitorMethod,
)


class LintRule(BatchableCSTVisitor):
    """
    Lint rule implemented using LibCST.

    To build a new lint rule, subclass this and `Implement a CST visitor
    <https://libcst.readthedocs.io/en/latest/tutorial.html#Build-Visitor-or-Transformer>`_.
    When a lint rule violation should be reported, use the :meth:`report` method.
    """

    METADATA_DEPENDENCIES: ClassVar[Collection[ProviderT]] = (PositionProvider,)
    """
    Required LibCST metadata providers
    """

    TAGS: Set[str] = set()
    "Arbitrary classification tags for use in configuration/selection"

    PYTHON_VERSION: str = ""
    """
    Compatible target Python versions, in `PEP 440 version specifier`__ format.

    __ https://peps.python.org/pep-0440/#version-specifiers
    """

    VALID: ClassVar[List[Union[str, ValidTestCase]]]
    "Test cases that should produce no errors/reports"

    INVALID: ClassVar[List[Union[str, InvalidTestCase]]]
    "Test cases that are expected to produce errors, with optional replacements"

    AUTOFIX = False  # set by __subclass_init__
    """
    Whether the lint rule contains an autofix.

    Set to ``True`` automatically when :attr:`INVALID` contains at least one
    test case that provides an expected replacment.
    """

    def __init__(self) -> None:
        self._violations: List[LintViolation] = []

    def __init_subclass__(cls) -> None:
        invalid: List[Union[str, InvalidTestCase]] = getattr(cls, "INVALID", [])
        for case in invalid:
            if isinstance(case, InvalidTestCase) and case.expected_replacement:
                cls.AUTOFIX = True
                return

    def __str__(self) -> str:
        return f"{self.__class__.__module__}:{self.__class__.__name__}"

    _visit_hook: Optional[VisitHook] = None

    def report(
        self,
        node: CSTNode,
        message: Optional[str] = None,
        *,
        position: Optional[Union[CodePosition, CodeRange]] = None,
        replacement: Optional[NodeReplacement] = None,
    ) -> None:
        """
        Report a lint rule violation.

        If `message` is not provided, ``self.MESSAGE`` will be used as a violation
        message. If neither of them are available, this method raises `ValueError`.

        The optional `position` parameter can override the location where the
        violation is reported. By default, the entire span of `node` is used. If
        `position` is a `CodePosition`, only a single character is marked.

        The optional `replacement` parameter can be used to provide an auto-fix for this
        lint violation. Replacing `node` with `replacement` should make the lint
        violation go away.
        """
        rule_name = type(self).__name__
        if not message:
            # backwards compat with Fixit 1.0 api
            message = getattr(self, "MESSAGE", None)
            if not message:
                raise ValueError(f"No message provided in {rule_name}")

        if position is None:
            position = self.get_metadata(PositionProvider, node)
        elif isinstance(position, CodePosition):
            end = replace(position, line=position.line + 1, column=0)
            position = CodeRange(start=position, end=end)
        self._violations.append(
            LintViolation(
                rule_name,
                range=position,
                message=message,
                node=node,
                replacement=replacement,
            )
        )

    def get_visitors(self) -> Mapping[str, VisitorMethod]:
        def _wrap(name: str, func: VisitorMethod) -> VisitorMethod:
            @functools.wraps(func)
            def wrapper(node: CSTNode) -> None:
                if self._visit_hook:
                    with self._visit_hook(name):
                        return func(node)
                return func(node)

            return wrapper

        return {
            name: _wrap(f"{type(self).__name__}.{name}", visitor)
            for (name, visitor) in super().get_visitors().items()
        }


# DEPRECATED: remove before stable 2.0 release
CstLintRule = LintRule
CSTLintRule = LintRule
