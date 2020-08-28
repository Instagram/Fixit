# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Collection, Sequence, Tuple

import libcst as cst
from libcst.metadata import ParentNodeProvider, PositionProvider

from fixit.common.base import CstContext, CstLintRule
from fixit.common.ignores import AllRulesType, IgnoreInfo, SuppressionComment
from fixit.common.insert_suppressions import (
    SuppressionComment as NewSuppressionComment,
    SuppressionCommentKind,
)


UNUSED_SUPPRESSION_COMMENT_MESSAGE = "Unused lint suppression. This comment is not suppressing lint errors and should be removed."
UNUSED_SUPPRESSION_CODES_IN_COMMENT_MESSAGE = "The codes `{lint_codes}` in this comment are not suppressing lint errors. They can be removed from this suppression."


# This is a special lint rule that should not be included in the fixit.rules package as it needs to run after all other rules.
class RemoveUnusedSuppressionsRule(CstLintRule):
    """
    The rule is run by `lint_file` after all other rules have finished running.
    It requires a completed reports dict in order to work properly.
    """

    METADATA_DEPENDENCIES = (ParentNodeProvider,)

    def __init__(self, context: CstContext,) -> None:
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

    def leave_EmptyLine(self, original_node: cst.EmptyLine) -> None:
        comment = original_node.comment
        if comment is None:
            return
        comment_physical_line = self.get_metadata(PositionProvider, comment).start.line
        local_supp_comments: Sequence[
            SuppressionComment
        ] = self.ignore_info.local_ignore_info.local_suppression_comments_by_line.get(
            comment_physical_line, []
        )

        if local_supp_comments:
            # Should only ever contain one element since a comment's 'local comment' will only be itself.
            assert len(local_supp_comments) == 1
            local_supp_comment = local_supp_comments[0]

            ignored_rules = local_supp_comment.ignored_rules
            # Just a check for the type-checker - it should never actually be AllRulesType
            # because we don't support that in lint-fixme/lint-ignore comments.
            # TODO: We can remove the AllRulesType check once we deprecate noqa.
            if isinstance(ignored_rules, AllRulesType):
                return

            # First find the suppressed codes that were included in the lint run. If the rule in question
            # was not included in this run, we CANNOT know for sure that this lint suppression is unused.
            ignored_rules_that_ran = {
                ig for ig in ignored_rules if ig in self.rule_names
            }

            if ignored_rules_that_ran == set(ignored_rules):
                if not local_supp_comment.used_by:
                    # If we're here, all of the codes in this suppression refer to rules that ran, and
                    # none of comment's codes suppress anything.
                    # If it's not the first line in the comment, we have already dealt with it, so skip
                    # all subsequent comment lines.
                    if comment.value == local_supp_comment.tokens[0].string:
                        # Report this comment and offer to remove it.
                        self._report_and_remove_logical_comment(
                            original_node, len(local_supp_comment.tokens)
                        )

            unreported_rules_that_ran = {
                ir
                for ir in ignored_rules_that_ran
                if not any(ir == report.code for report in local_supp_comment.used_by)
            }

            if unreported_rules_that_ran:
                new_codes = ", ".join(
                    [c for c in ignored_rules if c not in unreported_rules_that_ran]
                )

                kind = (
                    SuppressionCommentKind.FIXME
                    if local_supp_comment.kind == "fixme"
                    else SuppressionCommentKind.IGNORE
                )

                # Construct a new comment:
                new_lines = NewSuppressionComment(
                    kind=kind,
                    before_line=comment_physical_line + 1,
                    code=new_codes,
                    message=local_supp_comment.reason,
                ).to_lines()

                self._report_and_replace_logical_comment(
                    original_node,
                    len(local_supp_comment.tokens),
                    new_lines,
                    unreported_rules_that_ran,
                )

    def _get_parent_attribute(
        self, empty_line_node: cst.EmptyLine
    ) -> Tuple[cst.CSTNode, str, Sequence[cst.EmptyLine], int]:
        parent_node = self.get_metadata(ParentNodeProvider, empty_line_node)
        # EmptyLine nodes can be found in parent attributes `header`, `footer`, `leading_lines`, `lines_after_decorators` and `empty_lines`
        # The key is to find the right attribute.
        possible_attribute_names = [
            "header",
            "footer",
            "leading_lines",
            "lines_after_decorators",
            "empty_lines",
        ]
        for possible_attribute_name in possible_attribute_names:
            attribute_value = getattr(parent_node, possible_attribute_name, None)
            if attribute_value is not None:
                for idx, node in enumerate(attribute_value):
                    if node is empty_line_node:
                        # We have located the attribute
                        return (
                            parent_node,
                            possible_attribute_name,
                            attribute_value,
                            idx,
                        )

        # If we get here... we should never get here.
        raise ValueError(f"Unable to find parent attribute of {empty_line_node}.")

    def _report_and_replace_logical_comment(
        self,
        node_to_replace: cst.EmptyLine,
        lines_span: int,
        replacement_lines: Sequence[str],
        removed_codes: Collection[str],
    ) -> None:
        parent_node, attribute_name, attribute_value, idx = self._get_parent_attribute(
            node_to_replace
        )
        indent_value = node_to_replace.indent
        whitespace_value = node_to_replace.whitespace

        replacement_emptyline_nodes = [
            cst.EmptyLine(
                indent=indent_value,
                whitespace=whitespace_value,
                comment=cst.Comment(line),
            )
            for line in replacement_lines
        ]
        new_attribute_value = (
            list(av for av in attribute_value[:idx])
            + replacement_emptyline_nodes
            + list(av for av in attribute_value[idx + lines_span :])
        )

        self.report(
            parent_node,
            message=UNUSED_SUPPRESSION_CODES_IN_COMMENT_MESSAGE.format(
                lint_codes="`, `".join(r for r in removed_codes)
            ),
            replacement=parent_node.with_changes(
                **{attribute_name: new_attribute_value}
            ),
        )

    def _report_and_remove_logical_comment(
        self, node_to_remove: cst.EmptyLine, lines_span: int
    ) -> None:

        parent_node, attribute_name, attribute_value, idx = self._get_parent_attribute(
            node_to_remove
        )

        new_attribute_value = (
            list(av for av in attribute_value[:idx]) + list(av for av in attribute_value[idx + lines_span :])
        )

        self.report(
            parent_node,
            message=UNUSED_SUPPRESSION_COMMENT_MESSAGE,
            replacement=parent_node.with_changes(
                **{attribute_name: new_attribute_value}
            ),
        )
