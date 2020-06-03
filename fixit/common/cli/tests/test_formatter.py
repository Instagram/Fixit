# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path

import libcst as cst
from libcst.testing.utils import UnitTest

from fixit.common.cli.formatter import LintRuleReportFormatter, format_warning
from fixit.common.report import BaseLintRuleReport, CstLintRuleReport


class _ExtendedLintRuleReportFormatter(LintRuleReportFormatter):
    def _format_position(self, report: BaseLintRuleReport) -> str:
        return "<overridden position>"

    def _format_details_raw(self, report: BaseLintRuleReport) -> str:
        return "<overridden details_raw>"


class LintRuleReportFormatterTest(UnitTest):
    def setUp(self) -> None:
        self.report = CstLintRuleReport(
            file_path=Path("fake/path.py"),
            node=cst.parse_statement("pass\n"),
            code="IG00",
            message=(
                "Some long message that should span multiple lines.\n"
                + "\n"
                + "Another paragraph with more information about the lint rule."
            ),
            line=1,
            column=1,
            module=cst.MetadataWrapper(cst.parse_module(b"pass\n")),
            module_bytes=b"pass\n",
        )

    def test_format_full(self) -> None:
        full_formatter = LintRuleReportFormatter(width=20, compact=False)
        self.assertEqual(
            full_formatter.format(self.report),
            (
                "fake/path.py:1:1\n"
                + "    IG00 Some long\n"
                + "    message that\n"
                + "    should span\n"
                + "    multiple lines.\n"
                + "\n"
                + "    Another\n"
                + "    paragraph with\n"
                + "    more information\n"
                + "    about the lint\n"
                + "    rule."
            ),
        )

    def test_format_compact(self) -> None:
        compact_formatter = LintRuleReportFormatter(width=20, compact=True)
        self.assertEqual(compact_formatter.format(self.report), "fake/path.py:1:1")

    def test_format_extended(self) -> None:
        extended_formatter = _ExtendedLintRuleReportFormatter(width=100, compact=False)
        self.assertEqual(
            extended_formatter.format(self.report),
            "<overridden position>\n    <overridden details_raw>",
        )


class FormatWarningTest(UnitTest):
    def test_format_warning(self) -> None:
        self.assertEqual(
            format_warning("Some long warning message that should be wrapped.", 20),
            (
                "Warning: Some long\n"
                + "         warning\n"
                + "         message\n"
                + "         that should\n"
                + "         be wrapped."
            ),
        )
