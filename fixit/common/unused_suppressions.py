# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Sequence

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from fixit.common.base import CstContext, CstLintRule
from fixit.common.ignores import IgnoreInfo, SuppressionComment
from fixit.common.report import BaseLintRuleReport


UNUSED_SUPPRESSION_COMMENT_MESSAGE = "Unused lint suppression. This comment is not suppressing lint errors and should be removed."
UNUSED_SUPPRESSION_CODE_IN_COMMENT_MESSAGE = "The codes {lint_codes} in this comment are not suppressing lint errors. They can be removed from this suppression."


class RemoveUnusedSuppressionsRule(CstLintRule, cst.CSTVisitor):
    """
    The rule is run by `lint_file` after all other rules have finished running.
    It requires a completed reports dict in order to work properly.
    """

    def __init__(
        self,
        context: CstContext,
        reports: List[BaseLintRuleReport],
        ignore_info: IgnoreInfo,
    ) -> None:
        super().__init__(context)
        # Remove reports that should be ignored.
        self.context.reports = [
            r for r in reports if not ignore_info.should_ignore_report(r)
        ]
        self.ignore_info = ignore_info

    def leave_EmptyLine(self, original_node: cst.EmptyLine) -> None:
        comment = original_node.comment
        if comment is None:
            return
        comment_line = self.get_metadata(PositionProvider, comment).start.line
        local_supp_comments: Sequence[
            SuppressionComment
        ] = self.ignore_info.local_ignore_info.local_suppression_comments_by_line.get(
            comment_line, []
        )

        if local_supp_comments:
            # TODO check for unused codes in a comment that has many lint codes
            # unreported_rules = [ir for ir in sc.ignored_rules if not any(ir == report.code for report in sc.used_by)]
            if not local_supp_comments[0].used_by:
                # Remove this comment
                self.report(
                    original_node,
                    message=UNUSED_SUPPRESSION_COMMENT_MESSAGE,
                    replacement=cst.RemoveFromParent(),
                )


def visit_unused_suppressions_rule(
    wrapper: MetadataWrapper,
    context: CstContext,
    reports: List[BaseLintRuleReport],
    ignore_info: IgnoreInfo,
) -> List[BaseLintRuleReport]:
    instance = RemoveUnusedSuppressionsRule(context, reports, ignore_info)
    wrapper.visit(instance)
    return instance.context.reports
