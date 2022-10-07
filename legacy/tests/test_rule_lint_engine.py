# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path

import libcst as cst
from libcst.testing.utils import data_provider, UnitTest

from fixit import rule_lint_engine
from fixit.common.base import CstLintRule, LintConfig


class BadCallCstLintRule(CstLintRule):
    def visit_Call(self, node: cst.Call) -> None:
        func = node.func
        if isinstance(func, cst.Name) and func.value == "bad_call":
            self.report(node, "You made a bad call!")


class ParenthesizeAttributeLintRule(CstLintRule):
    """
    Transforms the following code:

        obj.attr.another_attr
    into:
        ((obj.attr).another_attr)
    This serves as an easy test case for overlapping lint fixes.
    """

    def visit_Attribute(self, node: cst.Attribute) -> None:
        rule_config = self.context.config.rule_config
        parenthesize_attribute_config = rule_config.get(self.__class__.__name__, {})
        if isinstance(
            parenthesize_attribute_config, dict
        ) and parenthesize_attribute_config.get("disabled", False):
            return
        if len(node.lpar) == 0:
            new_node = node.with_changes(
                lpar=[cst.LeftParen()], rpar=[cst.RightParen()]
            )
            self.report(
                node,
                "All attributes should be parenthesized.",
                replacement=new_node,
            )


class RuleLintEngineTest(UnitTest):
    @data_provider(
        {
            "good_call": {
                "source": b"good_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": False,
                "expected_report_count": 0,
                "use_noqa": False,
            },
            "bad_call": {
                "source": b"bad_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": False,
                "expected_report_count": 1,
                "use_noqa": False,
            },
            "multiple_bad_calls": {
                "source": b"bad_call()\nbad_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": False,
                "expected_report_count": 2,
                "use_noqa": False,
            },
            "bad_call_generated": {
                "source": b"'''@gen" + b"erated'''\nbad_call()",
                "use_ignore_byte_markers": True,
                "use_ignore_comments": False,
                "expected_report_count": 0,
                "use_noqa": False,
            },
            "bad_call_noqa": {
                "source": b"bad_call()  # noqa\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": True,
                "expected_report_count": 0,
                "use_noqa": True,
            },
            "bad_call_noqa_mixed": {
                "source": b"bad_call()  # noqa\nbad_call()  # missing noqa comment\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": True,
                "expected_report_count": 1,
                "use_noqa": True,
            },
            "bad_call_noqa_file": {
                "source": b"# noqa-file: BadCallCstLintRule: Test case\nbad_call()\nbad_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": True,
                "expected_report_count": 0,
                "use_noqa": True,
            },
        }
    )
    def test_lint_file(
        self,
        *,
        source: bytes,
        use_ignore_byte_markers: bool,
        use_ignore_comments: bool,
        expected_report_count: int,
        use_noqa: bool,
    ) -> None:
        reports = rule_lint_engine.lint_file(
            Path("dummy_filename.py"),
            source,
            use_ignore_byte_markers=use_ignore_byte_markers,
            use_ignore_comments=use_ignore_comments,
            config=LintConfig(use_noqa=use_noqa),
            rules={BadCallCstLintRule},
        )
        self.assertEqual(len(reports), expected_report_count)

    def test_lint_file_with_config(self) -> None:
        source = b"obj.attr.another_attr\n"
        config = LintConfig(
            rule_config={"ParenthesizeAttributeLintRule": {"disabled": True}},
        )

        reports = rule_lint_engine.lint_file(
            Path("dummy_file.py"),
            source,
            config=config,
            rules={ParenthesizeAttributeLintRule},
        )
        # Expect no reports cause disabled set to True
        self.assertEqual(len(reports), 0)

        config = LintConfig(
            rule_config={"ParenthesizeAttributeLintRule": {"disabled": False}}
        )
        reports = rule_lint_engine.lint_file(
            Path("dummy_file.py"),
            source,
            config=config,
            rules={ParenthesizeAttributeLintRule},
        )
        self.assertEqual(len(reports), 2)

    def test_lint_file_and_apply_patches(self) -> None:
        source = b"obj.attr.another_attr\n"
        expected_output = b"((obj.attr).another_attr)\n"

        result = rule_lint_engine.lint_file_and_apply_patches(
            Path("dummy_filename.py"),
            source,
            config=LintConfig(),
            rules={ParenthesizeAttributeLintRule},
        )
        self.assertEqual(len(result.reports), 2)
        self.assertEqual(result.patched_source, expected_output)
