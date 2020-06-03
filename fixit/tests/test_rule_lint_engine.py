# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path

import libcst as cst
from libcst.testing.utils import UnitTest, data_provider

from fixit import rule_lint_engine
from fixit.common.base import CstLintRule


class BadCallCstLintRule(CstLintRule):
    def visit_Call(self, node: cst.Call) -> None:
        func = node.func
        if isinstance(func, cst.Name) and func.value == "bad_call":
            self.report(node, "IG00 You made a bad call!")


class ParenthesizeAttributeLintRule(CstLintRule):
    """
    Transforms the following code:

        obj.attr.another_attr

    into:

        ((obj.attr).another_attr)

    This serves as an easy test case for overlapping lint fixes.
    """

    def visit_Attribute(self, node: cst.Attribute) -> None:
        if len(node.lpar) == 0:
            new_node = node.with_changes(
                lpar=[cst.LeftParen()], rpar=[cst.RightParen()]
            )
            self.report(
                node,
                "IG00 All attributes should be parenthesized.",
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
            },
            "bad_call": {
                "source": b"bad_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": False,
                "expected_report_count": 1,
            },
            "multiple_bad_calls": {
                "source": b"bad_call()\nbad_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": False,
                "expected_report_count": 2,
            },
            "bad_call_generated": {
                "source": b"'''@gen" + b"erated'''\nbad_call()",
                "use_ignore_byte_markers": True,
                "use_ignore_comments": False,
                "expected_report_count": 0,
            },
            "bad_call_noqa": {
                "source": b"bad_call()  # noqa\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": True,
                "expected_report_count": 0,
            },
            "bad_call_noqa_mixed": {
                "source": b"bad_call()  # noqa\nbad_call()  # missing noqa comment\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": True,
                "expected_report_count": 1,
            },
            "bad_call_noqa_file": {
                "source": b"# noqa-file: IG00: Test case\nbad_call()\nbad_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": True,
                "expected_report_count": 0,
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
    ) -> None:
        reports = rule_lint_engine.lint_file(
            Path("dummy_filename.py"),
            source,
            use_ignore_byte_markers=use_ignore_byte_markers,
            use_ignore_comments=use_ignore_comments,
            config={},
            rules=[BadCallCstLintRule],
        )
        self.assertEqual(len(reports), expected_report_count)

    def test_lint_file_and_apply_patches(self) -> None:
        source = b"obj.attr.another_attr\n"
        expected_output = b"((obj.attr).another_attr)\n"

        result = rule_lint_engine.lint_file_and_apply_patches(
            Path("dummy_filename.py"),
            source,
            config={},
            rules=[ParenthesizeAttributeLintRule],
        )
        self.assertEqual(len(result.reports), 2)
        self.assertEqual(result.patched_source, expected_output)
