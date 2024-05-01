# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Generator, Optional, Sequence

from libcst import (
    BaseSuite,
    Comma,
    Comment,
    CSTNode,
    Decorator,
    EmptyLine,
    IndentedBlock,
    LeftSquareBracket,
    Module,
    RightSquareBracket,
    SimpleStatementSuite,
    TrailingWhitespace,
)
from libcst.metadata import MetadataWrapper, ParentNodeProvider, PositionProvider


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
