# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Collection, List, Sequence, cast

import libcst as cst
from libcst.metadata import ParentNodeProvider, PositionProvider

from fixit.common.base import CstContext, CstLintRule
from fixit.common.ignores import AllRulesType, IgnoreInfo, SuppressionComment
from fixit.common.insert_suppressions import (
    DEFAULT_MIN_COMMENT_WIDTH,
    SuppressionComment as NewSuppressionComment,
    SuppressionCommentKind,
)


UNUSED_SUPPRESSION_COMMENT_MESSAGE = "Unused lint suppression. This comment is not suppressing lint errors and should be removed."
UNUSED_SUPPRESSION_CODES_IN_COMMENT_MESSAGE = "The codes `{lint_codes}` in this comment are not suppressing lint errors. They can be removed from this suppression."


def _compose_new_comment(
    local_supp_comment: SuppressionComment,
    unneeded_codes: Collection[str],
    comment_physical_line: int,
) -> Sequence[str]:
    ignored_rules = local_supp_comment.ignored_rules
    # Just a check for the type-checker - it should never actually be AllRulesType
    # because we don't support that in lint-fixme/lint-ignore comments.
    # TODO: We can remove the AllRulesType check once we deprecate noqa.
    if isinstance(ignored_rules, AllRulesType):
        raise ValueError(
            f"Got `AllRulesType` for the suppressed rules in comment on line {comment_physical_line}"
        )

    new_codes = ", ".join([c for c in ignored_rules if c not in unneeded_codes])
    if not new_codes:
        return []

    kind = (
        SuppressionCommentKind.FIXME
        if local_supp_comment.kind == "fixme"
        else SuppressionCommentKind.IGNORE
    )
    first_line = local_supp_comment.tokens[0]
    width = max(DEFAULT_MIN_COMMENT_WIDTH, len(first_line.string))

    # Construct a new comment.
    new_lines = NewSuppressionComment(
        kind=kind,
        before_line=comment_physical_line + 1,
        code=new_codes,
        message=local_supp_comment.reason,
        max_lines=len(local_supp_comment.tokens),
    ).to_lines(width)

    return new_lines


def _get_unused_codes_in_comment(
    local_supp_comment: SuppressionComment, ignored_rules_that_ran: Collection[str]
) -> Collection[str]:
    """Returns a subset of the rules in the comment which did not show up in any report."""
    return {
        ir
        for ir in ignored_rules_that_ran
        if not any(ir == report.code for report in local_supp_comment.used_by)
    }


def _modify_parent_attribute(
    parent_node: cst.CSTNode,
    attribute_name: str,
    idx_left: int,
    idx_right: int,
    list_to_insert: List[cst.EmptyLine],
) -> List[cst.EmptyLine]:
    """
    Replace the section starting at idx_left and ending at idx_right of the Sequence[cst.EmptyLine]-type attribute
    with `list_to_insert`.
    Returns the replacement attribute.
    """
    attribute_value = getattr(parent_node, attribute_name)
    attribute_value = cast(Sequence[cst.EmptyLine], attribute_value)
    return (
        list(attribute_value[:idx_left])
        + list_to_insert
        + list(attribute_value[idx_right:])
    )


# This is a special lint rule that should not be included in the fixit.rules package as it needs to run after all other rules.
class RemoveUnusedSuppressionsRule(CstLintRule):
    """
    The rule is run by `lint_file` after all other rules have finished running.
    It requires a completed reports dict in order to work properly.
    """

    METADATA_DEPENDENCIES = (ParentNodeProvider,)

    def __init__(
        self,
        context: CstContext,
    ) -> None:
        # TODO: Support Flake8 suppressions.
        super().__init__(context)
        ignore_info: object = self.context.config.rule_config[self.__class__.__name__][
            "ignore_info"
        ]
        rules: object = self.context.config.rule_config[self.__class__.__name__][
            "rules"
        ]
        assert isinstance(ignore_info, IgnoreInfo)
        assert isinstance(rules, list)

        self.ignore_info: IgnoreInfo = ignore_info
        self.rule_names: Collection[str] = {r.__name__ for r in rules}

    def _handle_emptyline_sequence_attribute(
        self, node: cst.CSTNode, attribute_name: str
    ) -> None:
        for idx, emptyline_node in enumerate(getattr(node, attribute_name)):
            comment = emptyline_node.comment
            if comment is None:
                continue
            comment_physical_line = self.get_metadata(
                PositionProvider, comment
            ).start.line
            local_supp_comments: Sequence[
                SuppressionComment
            ] = self.ignore_info.local_ignore_info.local_suppression_comments_by_line.get(
                comment_physical_line, []
            )
            if local_supp_comments:
                # We have found a `lint-ignore` or `lint-fixme` comment.
                # It should only ever contain one element since a comment's 'local comment' will only be itself.
                assert len(local_supp_comments) == 1
                local_supp_comment = local_supp_comments[0]
                if local_supp_comment.tokens[0].string == comment.value:
                    # We only call _handle_suppression_comment on the first line of the comment, it'll handle the remaining lines.
                    self._handle_suppression_comment(
                        node,
                        attribute_name,
                        idx,
                        local_supp_comment,
                        comment_physical_line,
                    )

    def _handle_node_with_leading_lines(self, node: cst.CSTNode) -> None:
        if hasattr(node, "leading_lines") and getattr(node, "leading_lines"):
            self._handle_emptyline_sequence_attribute(node, "leading_lines")

    def visit_Module(self, node: cst.Module) -> None:
        if node.header:
            self._handle_emptyline_sequence_attribute(node, "header")
        if node.footer:
            self._handle_emptyline_sequence_attribute(node, "footer")

    def visit_SimpleStatementLine(self, node: cst.SimpleStatementLine) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_If(self, node: cst.If) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_Else(self, node: cst.Else) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_BaseCompoundStatement(self, node: cst.BaseCompoundStatement) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_ExceptHandler(self, node: cst.ExceptHandler) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_Finally(self, node: cst.Finally) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_Try(self, node: cst.Try) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_Decorator(self, node: cst.Decorator) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        if node.leading_lines:
            self._handle_emptyline_sequence_attribute(node, "leading_lines")
        if node.lines_after_decorators:
            self._handle_emptyline_sequence_attribute(node, "lines_after_decorators")

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        if node.leading_lines:
            self._handle_emptyline_sequence_attribute(node, "leading_lines")
        if node.lines_after_decorators:
            self._handle_emptyline_sequence_attribute(node, "lines_after_decorators")

    def visit_With(self, node: cst.With) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_For(self, node: cst.For) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_While(self, node: cst.While) -> None:
        self._handle_node_with_leading_lines(node)

    def visit_ParenthesizedWhitespace(self, node: cst.ParenthesizedWhitespace) -> None:
        if node.empty_lines:
            self._handle_emptyline_sequence_attribute(node, "empty_lines")

    def _handle_suppression_comment(
        self,
        parent_node: cst.CSTNode,
        parent_attribute_name: str,
        index: int,
        local_supp_comment: SuppressionComment,
        comment_physical_line: int,
    ) -> None:
        ignored_rules = local_supp_comment.ignored_rules
        # Just a check for the type-checker - it should never actually be AllRulesType
        # because we don't support that in lint-fixme/lint-ignore comments.
        # TODO: We can remove the AllRulesType check once we deprecate noqa.
        if isinstance(ignored_rules, AllRulesType):
            return

        # First find the suppressed rules that were included in the lint run. If a rule was not included
        # in this run, we CANNOT know for sure that this lint suppression is unused.
        ignored_rules_that_ran = {ig for ig in ignored_rules if ig in self.rule_names}

        if not ignored_rules_that_ran:
            return

        lines_span = len(local_supp_comment.tokens)

        unneeded_codes = _get_unused_codes_in_comment(
            local_supp_comment, ignored_rules_that_ran
        )
        if unneeded_codes:
            new_comment_lines = _compose_new_comment(
                local_supp_comment, unneeded_codes, comment_physical_line
            )
            if not new_comment_lines:
                # If we're here, all of the codes in this suppression refer to rules that ran, and
                # none of comment's codes suppress anything, so we report this comment and offer to remove it.
                new_parent_attribute_value = _modify_parent_attribute(
                    parent_node, parent_attribute_name, index, index + lines_span, []
                )
                self.report(
                    parent_node,
                    message=UNUSED_SUPPRESSION_COMMENT_MESSAGE,
                    replacement=parent_node.with_changes(
                        **{parent_attribute_name: new_parent_attribute_value}
                    ),
                )
            else:
                node_to_replace = getattr(parent_node, parent_attribute_name)[index]
                replacement_emptyline_nodes = [
                    cst.EmptyLine(
                        indent=node_to_replace.indent,
                        whitespace=node_to_replace.whitespace,
                        comment=cst.Comment(line),
                    )
                    for line in new_comment_lines
                ]
                new_parent_attribute_value: List[
                    cst.EmptyLine
                ] = _modify_parent_attribute(
                    parent_node,
                    parent_attribute_name,
                    index,
                    index + lines_span,
                    replacement_emptyline_nodes,
                )

                self.report(
                    parent_node,
                    message=UNUSED_SUPPRESSION_CODES_IN_COMMENT_MESSAGE.format(
                        lint_codes="`, `".join(uc for uc in unneeded_codes)
                    ),
                    replacement=parent_node.with_changes(
                        **{parent_attribute_name: new_parent_attribute_value}
                    ),
                )
