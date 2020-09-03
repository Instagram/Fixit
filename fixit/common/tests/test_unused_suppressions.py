# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
from pathlib import Path
from typing import Collection, List, Optional, Type

import libcst as cst
from libcst.metadata import MetadataWrapper
from libcst.testing.utils import UnitTest, data_provider

from fixit.common.base import CstContext, CstLintRule, LintConfig
from fixit.common.comments import CommentInfo
from fixit.common.ignores import IgnoreInfo
from fixit.common.line_mapping import LineMappingInfo
from fixit.common.report import CstLintRuleReport
from fixit.common.unused_suppressions import (
    UNUSED_SUPPRESSION_CODES_IN_COMMENT_MESSAGE,
    UNUSED_SUPPRESSION_COMMENT_MESSAGE,
    RemoveUnusedSuppressionsRule,
    _compose_new_comment,
)
from fixit.common.utils import dedent_with_lstrip
from fixit.rule_lint_engine import _get_tokens, _visit_cst_rules_with_context


class UsedRule(CstLintRule):
    pass


class UsedRule2(CstLintRule):
    pass


FILE_PATH: Path = Path("fake/path.py")


class RemoveUnusedSuppressionsRuleTest(UnitTest):
    @data_provider(
        {
            "used_suppression_one_code_oneline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule],
                "rules_without_report": [],
                "suppressed_line": 2,
                "expected_unused_suppressions_report_messages": [],
            },
            "used_suppression_one_code_oneline_with_reason": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule: reason blah.
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule],
                "rules_without_report": [],
                "suppressed_line": 2,
                "expected_unused_suppressions_report_messages": [],
            },
            "used_suppression_one_code_multiline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule: reason
                    # lint: reason continued blah
                    # lint: blah blah.
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule],
                "rules_without_report": [],
                "suppressed_line": 4,
                "expected_unused_suppressions_report_messages": [],
            },
            "used_suppression_many_codes_oneline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule, UsedRule2
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule, UsedRule2],
                "rules_without_report": [],
                "suppressed_line": 2,
                "expected_unused_suppressions_report_messages": [],
            },
            "used_suppression_many_codes_multiline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule, UsedRule2:
                    # lint: reason blah blah.
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule, UsedRule2],
                "rules_without_report": [],
                "suppressed_line": 3,
                "expected_unused_suppressions_report_messages": [],
            },
            "unused_suppression_one_code_oneline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule: reason blah blah.
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule],
                "rules_without_report": [UsedRule],
                "suppressed_line": 2,
                "expected_unused_suppressions_report_messages": [
                    UNUSED_SUPPRESSION_COMMENT_MESSAGE
                ],
                "expected_replacements": [
                    dedent_with_lstrip(
                        """
                    foo = bar
                    """
                    )
                ],
            },
            "unused_suppression_one_code_multiline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule: reason
                    # lint: reason continued.
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule],
                "rules_without_report": [UsedRule],
                "suppressed_line": 3,
                "expected_unused_suppressions_report_messages": [
                    UNUSED_SUPPRESSION_COMMENT_MESSAGE
                ],
                "expected_replacements": [
                    dedent_with_lstrip(
                        """
                    foo = bar
                    """
                    )
                ],
            },
            "unused_suppression_many_codes_oneline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule, UsedRule2: reason
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule, UsedRule2],
                "rules_without_report": [UsedRule],
                "suppressed_line": 2,
                "expected_unused_suppressions_report_messages": [
                    UNUSED_SUPPRESSION_CODES_IN_COMMENT_MESSAGE.format(
                        lint_codes="UsedRule"
                    )
                ],
                "expected_replacements": [
                    dedent_with_lstrip(
                        """
                # lint-ignore: UsedRule2: reason
                foo = bar
                """
                    )
                ],
            },
            "unused_suppression_many_codes_multiline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule, UsedRule2: reason
                    # lint: reason continued.
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule, UsedRule2],
                "rules_without_report": [UsedRule],
                "suppressed_line": 3,
                "expected_unused_suppressions_report_messages": [
                    UNUSED_SUPPRESSION_CODES_IN_COMMENT_MESSAGE.format(
                        lint_codes="UsedRule"
                    )
                ],
                "expected_replacements": [
                    dedent_with_lstrip(
                        """
                # lint-ignore: UsedRule2: reason reason
                # lint: continued.
                foo = bar
                """
                    )
                ],
            },
            "unused_suppression_many_codes_all_unused": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule, UsedRule2: reason
                    # lint: reason continued.
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule, UsedRule2],
                "rules_without_report": [UsedRule, UsedRule2],
                "suppressed_line": 3,
                "expected_unused_suppressions_report_messages": [
                    UNUSED_SUPPRESSION_COMMENT_MESSAGE
                ],
                "expected_replacements": [
                    dedent_with_lstrip(
                        """
                        foo = bar
                        """
                    )
                ],
            },
            "multiple_suppressions": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule: first reason
                    # lint: first reason continued.
                    # lint-ignore: UsedRule2: second reason
                    # lint: second reason continued.
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule, UsedRule2],
                "rules_without_report": [UsedRule],
                "suppressed_line": 5,
                "expected_unused_suppressions_report_messages": [
                    UNUSED_SUPPRESSION_COMMENT_MESSAGE
                ],
                "expected_replacements": [
                    dedent_with_lstrip(
                        """
                # lint-ignore: UsedRule2: second reason
                # lint: second reason continued.
                foo = bar
                """
                    )
                ],
            },
            "multiple_unused_suppressions": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UsedRule: first reason
                    # lint: first reason continued.
                    # lint-ignore: UsedRule2: second reason
                    # lint: second reason continued.
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule, UsedRule2],
                "rules_without_report": [UsedRule, UsedRule2],
                "suppressed_line": 5,
                "expected_unused_suppressions_report_messages": [
                    UNUSED_SUPPRESSION_COMMENT_MESSAGE,
                    UNUSED_SUPPRESSION_COMMENT_MESSAGE,
                ],
                "expected_replacements": [
                    dedent_with_lstrip(
                        """
                        # lint-ignore: UsedRule2: second reason
                        # lint: second reason continued.
                        foo = bar
                        """
                    ),
                    dedent_with_lstrip(
                        """
                        # lint-ignore: UsedRule: first reason
                        # lint: first reason continued.
                        foo = bar
                    """
                    ),
                ],
            },
            "suppressions_with_unlinted_codes_oneline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UnusedRule
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule, UsedRule2],
                "rules_without_report": [],
                "suppressed_line": 2,
                "expected_unused_suppressions_report_messages": [],
            },
            "suppressions_with_unlinted_codes_multiline": {
                "source": dedent_with_lstrip(
                    """
                    # lint-ignore: UnusedRule: reason
                    # lint: reason continued
                    foo = bar
                    """
                ).encode(),
                "rules_in_lint_run": [UsedRule, UsedRule2],
                "rules_without_report": [],
                "suppressed_line": 3,
                "expected_unused_suppressions_report_messages": [],
            },
        }
    )
    def test(
        self,
        *,
        source: bytes,
        rules_in_lint_run: Collection[Type[CstLintRule]],
        rules_without_report: Collection[Type[CstLintRule]],
        suppressed_line: int,
        expected_unused_suppressions_report_messages: Collection[str],
        expected_replacements: Optional[List[str]] = None,
    ) -> None:
        reports = [
            CstLintRuleReport(
                file_path=FILE_PATH,
                node=cst.EmptyLine(),
                code=rule.__name__,
                message="message",
                line=suppressed_line,
                column=0,
                module=cst.MetadataWrapper(cst.parse_module(source)),
                module_bytes=source,
            )
            for rule in rules_in_lint_run
            if rule not in rules_without_report
        ]
        tokens = _get_tokens(source)
        ignore_info = IgnoreInfo.compute(
            comment_info=CommentInfo.compute(tokens=tokens),
            line_mapping_info=LineMappingInfo.compute(tokens=tokens),
        )
        cst_wrapper = MetadataWrapper(cst.parse_module(source), unsafe_skip_copy=True)
        config = LintConfig(
            rule_config={
                RemoveUnusedSuppressionsRule.__name__: {
                    "ignore_info": ignore_info,
                    "rules": rules_in_lint_run,
                }
            }
        )
        unused_suppressions_context = CstContext(cst_wrapper, source, FILE_PATH, config)
        for report in reports:
            ignore_info.should_ignore_report(report)
        _visit_cst_rules_with_context(
            cst_wrapper, [RemoveUnusedSuppressionsRule], unused_suppressions_context
        )

        messages = []
        patches = []
        for report in unused_suppressions_context.reports:
            messages.append(report.message)
            patches.append(report.patch)

        self.assertEqual(messages, expected_unused_suppressions_report_messages)
        if expected_replacements is None:
            self.assertEqual(len(patches), 0)
        else:
            self.assertEqual(len(patches), len(expected_replacements))

            for idx, patch in enumerate(patches):
                replacement = patch.apply(source.decode())
                self.assertEqual(replacement, expected_replacements[idx])

    def test_compose_new_comment_oneline(self) -> None:
        source = dedent_with_lstrip("# lint-fixme: UsedRule, UsedRule2: reason...")
        tokens = _get_tokens(source.encode())
        ignore_info = IgnoreInfo.compute(
            comment_info=CommentInfo.compute(tokens=tokens),
            line_mapping_info=LineMappingInfo.compute(tokens=tokens),
        )
        local_suppression_comments = (
            ignore_info.local_ignore_info.local_suppression_comments_by_line[1]
        )
        self.assertEqual(len(local_suppression_comments), 1)
        local_suppression_comment = local_suppression_comments[0]

        # First code unneeded.
        unneeded_codes = ["UsedRule"]
        new_comment_lines = _compose_new_comment(
            local_suppression_comment, unneeded_codes, 1
        )
        expected_new_lines = ["# lint-fixme: UsedRule2: reason..."]
        self.assertEqual(new_comment_lines, expected_new_lines)

        # Second code unneeded.
        unneeded_codes = ["UsedRule2"]
        new_comment_lines = _compose_new_comment(
            local_suppression_comment, unneeded_codes, 1
        )
        expected_new_lines = ["# lint-fixme: UsedRule: reason..."]
        self.assertEqual(new_comment_lines, expected_new_lines)

        # Both codes unneded.
        unneeded_codes = ["UsedRule", "UsedRule2"]
        new_comment_lines = _compose_new_comment(
            local_suppression_comment, unneeded_codes, 1
        )
        expected_new_lines = []
        self.assertEqual(new_comment_lines, expected_new_lines)

        # Both codes needed.
        unneeded_codes = []
        new_comment_lines = _compose_new_comment(
            local_suppression_comment, unneeded_codes, 1
        )
        # Should be unchanged.
        expected_new_lines = [source]
        self.assertEqual(new_comment_lines, expected_new_lines)

    def test_compose_new_comment_multiline(self) -> None:
        source = dedent_with_lstrip(
            """
            # lint-fixme: UsedRule, UsedRule2: reason...
            # lint: reason continued
            """
        )
        tokens = _get_tokens(source.encode())
        ignore_info = IgnoreInfo.compute(
            comment_info=CommentInfo.compute(tokens=tokens),
            line_mapping_info=LineMappingInfo.compute(tokens=tokens),
        )
        local_suppression_comments = (
            ignore_info.local_ignore_info.local_suppression_comments_by_line[1]
        )
        self.assertEqual(len(local_suppression_comments), 1)
        local_suppression_comment = local_suppression_comments[0]

        # First code unneeded.
        unneeded_codes = ["UsedRule"]
        new_comment_lines = _compose_new_comment(
            local_suppression_comment, unneeded_codes, 1
        )
        expected_new_lines = [
            "# lint-fixme: UsedRule2: reason... reason",
            "# lint: continued",
        ]
        self.assertEqual(new_comment_lines, expected_new_lines)

        # Second code unneeded.
        unneeded_codes = ["UsedRule2"]
        new_comment_lines = _compose_new_comment(
            local_suppression_comment, unneeded_codes, 1
        )
        expected_new_lines = [
            "# lint-fixme: UsedRule: reason... reason",
            "# lint: continued",
        ]
        self.assertEqual(new_comment_lines, expected_new_lines)

        # Both codes unneded.
        unneeded_codes = ["UsedRule", "UsedRule2"]
        new_comment_lines = _compose_new_comment(
            local_suppression_comment, unneeded_codes, 1
        )
        expected_new_lines = []
        self.assertEqual(new_comment_lines, expected_new_lines)

        # Both codes needed.
        unneeded_codes = []
        new_comment_lines = _compose_new_comment(
            local_suppression_comment, unneeded_codes, 1
        )
        expected_new_lines = [
            "# lint-fixme: UsedRule, UsedRule2: reason...",
            "# lint: reason continued",
        ]
        self.assertEqual(new_comment_lines, expected_new_lines)
