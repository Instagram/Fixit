# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
All of the ignore logic for the lint engine.
"""

import tokenize
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import (
    Collection,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from fixit.common.base import CstLintRule
from fixit.common.comments import CommentInfo
from fixit.common.config import (
    FLAKE8_NOQA_FILE,
    LINT_IGNORE_REGEXP,
    NOQA_FILE_RULE,
    NOQA_INLINE_REGEXP,
)
from fixit.common.insert_suppressions import BODY_PREFIX_WITH_SPACE
from fixit.common.line_mapping import LineMappingInfo
from fixit.common.pseudo_rule import PseudoLintRule
from fixit.common.report import BaseLintRuleReport


_LintRuleT = Union[Type[CstLintRule], Type[PseudoLintRule]]


class AllRulesType(Enum):
    ALL_RULES = 0


IgnoredRules = Union[Collection[str], AllRulesType]


class SuppressionCommentKind(Enum):
    NOQA = "noqa"
    LINT_IGNORE = "lint-ignore"  # also includes lint-fixme comments


class SuppressionComment:
    ignored_rules: IgnoredRules
    # a lint-fixme or lint-ignore comment can span multiple lines, so it may be composed
    # of multiple tokens.
    tokens: Sequence[tokenize.TokenInfo]
    used_by: List[BaseLintRuleReport]
    kind: str
    reason: Optional[str]

    def __init__(
        self,
        ignored_rules: IgnoredRules,
        tokens: Sequence[tokenize.TokenInfo],
        kind: str,
        reason: Optional[str] = None,
    ) -> None:
        self.ignored_rules = ignored_rules
        self.tokens = tokens
        self.used_by = []
        self.kind = kind
        self.reason = reason

    def should_ignore_report(self, report: BaseLintRuleReport) -> bool:
        ignored_rules = self.ignored_rules
        return isinstance(ignored_rules, AllRulesType) or report.code in ignored_rules

    def mark_used_by(self, report: BaseLintRuleReport) -> None:
        self.used_by.append(report)

    def __repr__(self) -> str:
        return "\n".join(t.string for t in self.tokens)


# Loosely based on flake8's parse_comma_separated_list
# https://gitlab.com/pycqa/flake8/blob/52d88d8ca7208d1edc554b41a/src/flake8/utils.py#L17
# Used for parsing `# lint-fixme`, `# lint-ignore`, `# noqa` and `# noqa-file`
def _parse_comma_separated_rules(rules_str: Optional[str]) -> IgnoredRules:
    if rules_str is None:
        return AllRulesType.ALL_RULES
    item_gen = (c.strip() for c in rules_str.split(","))
    rules_list = [item for item in item_gen if item]
    return rules_list if rules_list else AllRulesType.ALL_RULES


@dataclass(frozen=True)
class GlobalIgnoreInfo:
    # Rules that are ignored on every line of the file (e.g. due to a `# noqa-file`).
    globally_ignored_rules: IgnoredRules

    def should_evaluate_rule(self, rule: _LintRuleT) -> bool:
        # TODO: We need a way to map lint codes back to the rules they come from so that
        # we can avoid executing them.
        return not isinstance(self.globally_ignored_rules, AllRulesType)

    def should_ignore_report(self, report: BaseLintRuleReport) -> bool:
        globally_ignored_rules = self.globally_ignored_rules
        return (
            isinstance(globally_ignored_rules, AllRulesType)
            or report.code in globally_ignored_rules
        )

    @staticmethod
    def compute(*, comment_info: CommentInfo) -> "GlobalIgnoreInfo":
        ignored_rules = set()
        for tok in comment_info.comments_on_own_line:
            if FLAKE8_NOQA_FILE.fullmatch(tok.string):
                # For backwards compatibility
                return GlobalIgnoreInfo(globally_ignored_rules=AllRulesType.ALL_RULES)
            file_rule_match = NOQA_FILE_RULE.fullmatch(tok.string)
            if file_rule_match:
                newly_ignored_rules = _parse_comma_separated_rules(
                    file_rule_match.group("codes")
                )
                if isinstance(newly_ignored_rules, AllRulesType):
                    raise ValueError("A `# noqa-file` must specify codes to ignore")
                ignored_rules.update(newly_ignored_rules)
        return GlobalIgnoreInfo(globally_ignored_rules=ignored_rules)


@dataclass(frozen=True)
class LocalIgnoreInfo:
    local_suppression_comments: Collection[SuppressionComment]
    # Maps logical line numbers to the relevant suppression comments for that line.
    local_suppression_comments_by_line: Mapping[int, Sequence[SuppressionComment]]
    # We use this to find the next non-empty logical line before looking up
    # locally_ignored_rules.
    line_mapping_info: LineMappingInfo

    def should_ignore_report(self, report: BaseLintRuleReport) -> bool:
        logical_line = self.line_mapping_info.physical_to_logical[report.line]
        suppression_comments = self.local_suppression_comments_by_line.get(
            logical_line, []
        )
        for comment in suppression_comments:
            if comment.should_ignore_report(report):
                comment.mark_used_by(report)
                return True
        return False

    @staticmethod
    def get_all_tokens_and_full_reason(
        tokens: List[tokenize.TokenInfo],
        comment_lines: Iterator[tokenize.TokenInfo],
        end_line: int,
        reason: Optional[str],
    ) -> Tuple[List[tokenize.TokenInfo], Optional[str], Optional[tokenize.TokenInfo]]:
        next_comment_line = next(comment_lines, None)
        while next_comment_line is not None and next_comment_line.start[0] < end_line:
            if not next_comment_line.string.startswith(BODY_PREFIX_WITH_SPACE):
                break
            reason_contd = next_comment_line.string.split(BODY_PREFIX_WITH_SPACE, 1)[1]
            reason = (
                " ".join([reason, reason_contd]) if reason is not None else reason_contd
            )
            tokens.append(next_comment_line)
            next_comment_line = next(comment_lines, None)

        return tokens, reason, next_comment_line

    @staticmethod
    def compute(
        *, comment_info: CommentInfo, line_mapping_info: LineMappingInfo
    ) -> "LocalIgnoreInfo":
        local_suppression_comments: List[SuppressionComment] = []
        local_suppression_comments_by_line: Dict[
            int, List[SuppressionComment]
        ] = defaultdict(list)

        # New `# lint-fixme` and `# lint-ignore` comments. These are preferred over
        # legacy `# noqa` comments.
        comments_on_own_line_iter = iter(comment_info.comments_on_own_line)
        next_comment_line: Optional[tokenize.TokenInfo] = next(
            comments_on_own_line_iter, None
        )

        while next_comment_line is not None:
            match = LINT_IGNORE_REGEXP.fullmatch(next_comment_line.string)
            if match is not None:
                # We are at the *start* of a suppression comment. There may be more physical lines
                # to the comment. We assume any lines starting with `# lint: ` are a continuation.
                start_line = next_comment_line.start[0]
                end_line = line_mapping_info.get_next_non_empty_logical_line(start_line)
                assert end_line is not None, "Failed to get next non-empty logical line"

                (
                    tokens,
                    reason,
                    next_comment_line,
                ) = LocalIgnoreInfo.get_all_tokens_and_full_reason(
                    [next_comment_line],
                    comments_on_own_line_iter,
                    end_line,
                    match.group("reason"),
                )

                codes = _parse_comma_separated_rules(match.group("codes"))
                # Construct the SuppressionComment with all the information.
                comment = SuppressionComment(codes, tokens, match.group(1), reason)

                local_suppression_comments.append(comment)

                for tok in tokens:
                    local_suppression_comments_by_line[tok.start[0]].append(comment)

                # Finally we want to map the suppressed line of code to this suppression comment.
                local_suppression_comments_by_line[end_line].append(comment)
            else:
                next_comment_line = next(comments_on_own_line_iter, None)

        # Legacy inline `# noqa` comments. This matches flake8's behavior.
        # Process these after `# lint-ignore` comments, because in the case of duplicate
        # or overlapping ignores, we'd prefer to mark the noqa as unused, instead of the
        # more modern `# lint-ignore` comment.
        for tok in comment_info.comments:
            match = NOQA_INLINE_REGEXP.search(tok.string)
            if match:
                normalized_line = line_mapping_info.physical_to_logical[tok.start[0]]
                codes = _parse_comma_separated_rules(match.group("codes"))
                comment = SuppressionComment(codes, [tok], kind="noqa")
                local_suppression_comments.append(comment)
                local_suppression_comments_by_line[normalized_line].append(comment)

        return LocalIgnoreInfo(
            local_suppression_comments,
            dict(local_suppression_comments_by_line),  # no longer a defaultdict
            line_mapping_info,
        )


@dataclass(frozen=True)
class IgnoreInfo:
    global_ignore_info: GlobalIgnoreInfo
    local_ignore_info: LocalIgnoreInfo
    suppression_comments: Collection[SuppressionComment]

    def should_evaluate_rule(self, rule: _LintRuleT) -> bool:
        """
        Call this before evaluating lint rules to filter out rules that will be entirely
        ignored.
        """
        return self.global_ignore_info.should_evaluate_rule(rule)

    def should_ignore_report(self, report: BaseLintRuleReport) -> bool:
        return self.global_ignore_info.should_ignore_report(
            report
        ) or self.local_ignore_info.should_ignore_report(report)

    @staticmethod
    def compute(
        *, comment_info: CommentInfo, line_mapping_info: LineMappingInfo
    ) -> "IgnoreInfo":
        global_ignore_info = GlobalIgnoreInfo.compute(comment_info=comment_info)
        local_ignore_info = LocalIgnoreInfo.compute(
            comment_info=comment_info, line_mapping_info=line_mapping_info
        )
        return IgnoreInfo(
            global_ignore_info,
            local_ignore_info,
            # TODO: compute global suppression comments and merge them here
            local_ignore_info.local_suppression_comments,
        )
