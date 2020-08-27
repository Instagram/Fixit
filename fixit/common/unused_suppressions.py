# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Sequence

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from fixit.common.base import CstContext, CstLintRule
from fixit.common.config import LINT_IGNORE_REGEXP
from fixit.common.ignores import AllRulesType, IgnoreInfo, SuppressionComment
from fixit.common.report import BaseLintRuleReport


UNUSED_SUPPRESSION_COMMENT_MESSAGE = "Unused lint suppression. This comment is not suppressing lint errors and should be removed."
UNUSED_SUPPRESSION_CODE_IN_COMMENT_MESSAGE = "The codes `{lint_codes}` in this comment are not suppressing lint errors. They can be removed from this suppression."


# This is a special lint rule that should not be included in the fixit.rules package as it needs to run after all other rules.
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
            local_supp_comment = local_supp_comments[0]
            if not local_supp_comment.used_by:
                # Remove this comment
                self.report(
                    original_node,
                    message=UNUSED_SUPPRESSION_COMMENT_MESSAGE,
                    replacement=cst.RemoveFromParent(),
                )
            else:
                ignored_rules = local_supp_comment.ignored_rules
                # Check if it's trying to suppress multiple rules.
                # Just a check for the type-checker - it should never actually be AllRulesType
                # because we don't support that in lint-fixme/lint-ignore comments.
                # TODO: We can remove the AllRulesType check once we deprecate noqa.
                if (
                    not isinstance(ignored_rules, AllRulesType)
                    and len(ignored_rules) > 1
                ):
                    unreported_rules = [
                        ir
                        for ir in ignored_rules
                        if not any(
                            ir == report.code for report in local_supp_comment.used_by
                        )
                    ]

                    match = LINT_IGNORE_REGEXP.fullmatch(comment.value)
                    if match is not None:
                        codes = match.group("codes").split(", ")
                        new_codes = ", ".join(
                            [c for c in codes if c not in unreported_rules]
                        )
                        supp_type = match.group(1)
                        reason = match.group("reason")
                        postfix = f": {reason}" if reason is not None else ""
                        new_comment_value = f"# lint-{supp_type}: {new_codes}{postfix}"
                        self.report(
                            original_node,
                            message=UNUSED_SUPPRESSION_CODE_IN_COMMENT_MESSAGE.format(
                                lint_codes="`, `".join(unreported_rules)
                            ),
                            replacement=original_node.with_changes(
                                comment=cst.Comment(new_comment_value)
                            ),
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
