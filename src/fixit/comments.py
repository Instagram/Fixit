# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Generator, List, Optional, Sequence

from libcst import (
    BaseSuite,
    Comma,
    Comment,
    CSTNode,
    Decorator,
    EmptyLine,
    ensure_type,
    IndentedBlock,
    LeftSquareBracket,
    matchers as m,
    Module,
    ParenthesizedWhitespace,
    RightSquareBracket,
    SimpleStatementSuite,
    SimpleWhitespace,
    TrailingWhitespace,
)
from libcst.metadata import MetadataWrapper, ParentNodeProvider, PositionProvider

from .ftypes import LintIgnore, LintIgnoreStyle


def node_comments(
    node: CSTNode, metadata: MetadataWrapper
) -> Generator[Comment, None, None]:
    """
    Yield all comments associated with the given node.

    Includes comments from both leading comments and trailing inline comments.
    """
    parent_nodes = metadata.resolve(ParentNodeProvider)
    positions = metadata.resolve(PositionProvider)
    target_line = positions[node].end.line

    def gen(node: CSTNode) -> Generator[Comment, None, None]:
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
                yield tw.comment

            comma: Optional[Comma] = getattr(node, "comma", None)
            if isinstance(comma, Comma):
                tw = getattr(comma.whitespace_after, "first_line", None)
                if tw and tw.comment:
                    yield tw.comment

            rb: Optional[RightSquareBracket] = getattr(node, "rbracket", None)
            if rb is not None:
                tw = getattr(rb.whitespace_before, "first_line", None)
                if tw and tw.comment:
                    yield tw.comment

            el: Optional[Sequence[EmptyLine]] = None
            lb: Optional[LeftSquareBracket] = getattr(node, "lbracket", None)
            if lb is not None:
                el = getattr(lb.whitespace_after, "empty_lines", None)
                if el is not None:
                    for line in el:
                        if line.comment:
                            yield line.comment

            el = getattr(node, "lines_after_decorators", None)
            if el is not None:
                for line in el:
                    if line.comment:
                        yield line.comment

            ll: Optional[Sequence[EmptyLine]] = getattr(node, "leading_lines", None)
            if ll is not None:
                for line in ll:
                    if line.comment:
                        yield line.comment
                if not isinstance(node, Decorator):
                    # stop looking once we've gone up far enough for leading_lines,
                    # even if there are no comment lines here at all
                    break

            parent = parent_nodes.get(node)
            if parent is None:
                break
            node = parent

        # comments at the start of the file are part of the module header rather than
        # part of the first statement's leading_lines, so we need to look there in case
        # the reported node is part of the first statement.
        if isinstance(node, Module):
            for line in node.header:
                if line.comment:
                    yield line.comment
        else:
            parent = parent_nodes.get(node)
            if isinstance(parent, Module) and parent.body and parent.body[0] == node:
                for line in parent.header:
                    if line.comment:
                        yield line.comment

    # wrap this in a pass-through generator so that we can easily filter the results
    # to only include comments that are located on or before the line containing
    # the original node that we're searching from
    yield from (c for c in gen(node) if positions[c].end.line <= target_line)


def node_nearest_comment(node: CSTNode, metadata: MetadataWrapper) -> CSTNode:
    """
    Return the nearest tree node where a suppression comment could be added.
    """
    parent_nodes = metadata.resolve(ParentNodeProvider)
    positions = metadata.resolve(PositionProvider)
    node_line = positions[node].start.line

    while not isinstance(node, Module):
        if hasattr(node, "comment"):
            return node

        if hasattr(node, "trailing_whitespace"):
            tw = ensure_type(node.trailing_whitespace, TrailingWhitespace)
            if tw and positions[tw].start.line == node_line:
                if tw.comment:
                    return tw.comment
                else:
                    return tw

        if hasattr(node, "comma"):
            if m.matches(
                node.comma,
                m.Comma(
                    whitespace_after=m.ParenthesizedWhitespace(
                        first_line=m.TrailingWhitespace()
                    )
                ),
            ):
                return ensure_type(
                    node.comma.whitespace_after.first_line, TrailingWhitespace
                )

        if hasattr(node, "rbracket"):
            tw = ensure_type(
                ensure_type(
                    node.rbracket.whitespace_before,
                    ParenthesizedWhitespace,
                ).first_line,
                TrailingWhitespace,
            )
            if positions[tw].start.line == node_line:
                return tw

        if hasattr(node, "leading_lines"):
            return node

        parent = parent_nodes.get(node)
        if parent is None:
            break
        node = parent

    raise RuntimeError("could not find nearest comment node")


def add_suppression_comment(
    module: Module,
    node: CSTNode,
    metadata: MetadataWrapper,
    name: str,
    style: LintIgnoreStyle = LintIgnoreStyle.fixme,
) -> Module:
    """
    Return a modified tree that includes a suppression comment for the given rule.
    """
    # reuse an existing suppression directive if available rather than making a new one
    for comment in node_comments(node, metadata):
        lint_ignore = LintIgnore.parse(comment.value)
        if lint_ignore and lint_ignore.style == style:
            if name in lint_ignore.names:
                return module  # already suppressed
            lint_ignore.names.add(name)
            return module.with_deep_changes(comment, value=str(lint_ignore))

    # no existing directives, find the "nearest" location and add a comment there
    target = node_nearest_comment(node, metadata)
    lint_ignore = LintIgnore(style, {name})

    if isinstance(target, Comment):
        lint_ignore.prefix = target.value.strip()
        return module.with_deep_changes(target, value=str(lint_ignore))

    if isinstance(target, TrailingWhitespace):
        if target.comment:
            lint_ignore.prefix = target.comment.value.strip()
            return module.with_deep_changes(target.comment, value=str(lint_ignore))
        else:
            return module.with_deep_changes(
                target,
                comment=Comment(str(lint_ignore)),
                whitespace=SimpleWhitespace("  "),
            )

    if hasattr(target, "leading_lines"):
        ll: List[EmptyLine] = list(target.leading_lines or ())
        ll.append(EmptyLine(comment=Comment(str(lint_ignore))))
        return module.with_deep_changes(target, leading_lines=ll)

    raise RuntimeError("failed to add suppression comment")
