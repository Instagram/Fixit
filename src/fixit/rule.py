# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations

import functools
from dataclasses import replace
from typing import (
    ClassVar,
    Collection,
    Generator,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Union,
)

from libcst import (
    BaseSuite,
    BatchableCSTVisitor,
    CSTNode,
    EmptyLine,
    IndentedBlock,
    Module,
    SimpleStatementSuite,
    TrailingWhitespace,
)
from libcst.metadata import (
    CodePosition,
    CodeRange,
    ParentNodeProvider,
    PositionProvider,
    ProviderT,
)

from .ftypes import (
    InvalidTestCase,
    LintIgnoreRegex,
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

    name: str
    """
    Friendly name of this lint rule class, without any "Rule" suffix.
    """

    def __init__(self) -> None:
        self._violations: List[LintViolation] = []
        self.name = self.__class__.__name__
        if self.name.endswith("Rule"):
            self.name = self.name[:-4]

    def __init_subclass__(cls) -> None:
        if ParentNodeProvider not in cls.METADATA_DEPENDENCIES:
            cls.METADATA_DEPENDENCIES = (*cls.METADATA_DEPENDENCIES, ParentNodeProvider)

        invalid: List[Union[str, InvalidTestCase]] = getattr(cls, "INVALID", [])
        for case in invalid:
            if isinstance(case, InvalidTestCase) and case.expected_replacement:
                cls.AUTOFIX = True
                return

    def __str__(self) -> str:
        return f"{self.__class__.__module__}:{self.__class__.__name__}"

    _visit_hook: Optional[VisitHook] = None

    def node_comments(self, node: CSTNode) -> Generator[str, None, None]:
        """
        Yield all comments associated with the given node.

        Includes comments from both leading comments and trailing inline comments.
        """
        while not isinstance(node, Module):
            # trailing_whitespace can either be a property of the node itself, or in
            # case of blocks, be part of the block's body element
            tw: Optional[TrailingWhitespace] = getattr(
                node, "trailing_whitespace", None
            )
            if tw is None:
                body: Optional[BaseSuite] = getattr(node, "body", None)
                if isinstance(body, SimpleStatementSuite):
                    tw = body.trailing_whitespace
                elif isinstance(body, IndentedBlock):
                    tw = body.header

            if tw and tw.comment:
                yield tw.comment.value

            ll: Optional[Sequence[EmptyLine]] = getattr(node, "leading_lines", None)
            if ll is not None:
                for line in ll:
                    if line.comment:
                        yield line.comment.value
                # stop looking once we've gone up far enough for leading_lines,
                # even if there are no comment lines here at all
                break

            node = self.get_metadata(ParentNodeProvider, node)

        # comments at the start of the file are part of the module header rather than
        # part of the first statement's leading_lines, so we need to look there in case
        # the reported node is part of the first statement.
        parent = self.get_metadata(ParentNodeProvider, node)
        if isinstance(parent, Module) and parent.body and parent.body[0] == node:
            for line in parent.header:
                if line.comment:
                    yield line.comment.value

    def ignore_lint(self, node: CSTNode) -> bool:
        """
        Whether to ignore a violation for a given node.

        Returns true if any ``# lint-ignore`` or ``# lint-fixme`` directives match the
        current rule by name, or if the directives have no rule names listed.
        """
        rule_names = (self.name, self.name.lower())
        for comment in self.node_comments(node):
            if match := LintIgnoreRegex.match(comment):
                _style, names = match.groups()

                # directive
                if names is None:
                    return True

                # directive: RuleName
                for name in (n.strip() for n in names.split(",")):
                    if name.endswith("Rule"):
                        name = name[:-4]
                    if name in rule_names:
                        return True

        return False

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
        if self.ignore_lint(node):
            # TODO: consider logging/reporting this somewhere?
            return

        if not message:
            # backwards compat with Fixit 1.0 api
            message = getattr(self, "MESSAGE", None)
            if not message:
                raise ValueError(f"No message provided in {self.name}")

        if position is None:
            position = self.get_metadata(PositionProvider, node)
        elif isinstance(position, CodePosition):
            end = replace(position, line=position.line + 1, column=0)
            position = CodeRange(start=position, end=end)

        self._violations.append(
            LintViolation(
                self.name,
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
