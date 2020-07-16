# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, List, Sequence
from unittest.mock import mock_open, patch

from libcst import Module
from libcst.testing.utils import UnitTest

from fixit.common.base import CstLintRule
from fixit.common.cli import LintOpts, get_file_lint_result_json
from fixit.common.report import (
    BaseLintRuleReport,
    LintFailureReportBase,
    LintSuccessReportBase,
)


class FakeRule(CstLintRule):
    def visit_Module(self, node: Module) -> None:
        self.report(node, "IG00 dummy message")


@dataclass(frozen=True)
class FakeLintSuccessReport(LintSuccessReportBase):
    path: str
    status: str
    reports: Collection[str]

    @staticmethod
    def create_reports(
        path: Path, reports: Collection[BaseLintRuleReport], global_list: List[str],
    ) -> Sequence[LintSuccessReportBase]:
        global_list.append(str(path))
        return [FakeLintSuccessReport(str(path), "success", ["fake picklable report"])]


class LintOptsTest(UnitTest):
    def setUp(self) -> None:
        self.global_list = []
        self.opts = LintOpts(
            [FakeRule],
            FakeLintSuccessReport,
            LintFailureReportBase,
            extra={"global_list": self.global_list},
        )

    @patch("builtins.open", mock_open(read_data=b"test"))
    def test_opts_with_extra(self) -> None:
        path = Path("fake/path.py")
        json_results = get_file_lint_result_json(path, self.opts)

        # Assert global list has been modified
        self.assertEqual(list(self.global_list), [str(path)])

        # Assert the rest of the reporting functionality is as expected
        self.assertEqual(len(json_results), 1)
        json_for_file = json.loads(json_results[0])
        self.assertEqual(json_for_file["reports"][0], "fake picklable report")

    @patch("builtins.open", mock_open(read_data=b"test"))
    def test_opts_with_extra_multiple_paths(self) -> None:
        paths = [Path("fake/path1.py"), Path("fake/path2.py")]
        json_results_path1 = get_file_lint_result_json(paths[0], self.opts)
        json_results_path2 = get_file_lint_result_json(paths[1], self.opts)

        # Assert global list has been modified as expected
        self.assertEqual(list(self.global_list), [str(p) for p in paths])

        # Assert the rest of the reporting functionality is as expected
        self.assertEqual(len(json_results_path1), 1)
        json_for_file_1 = json.loads(json_results_path1[0])
        self.assertEqual(json_for_file_1["reports"][0], "fake picklable report")

        self.assertEqual(len(json_results_path2), 1)
        json_for_file_2 = json.loads(json_results_path2[0])
        self.assertEqual(json_for_file_2["reports"][0], "fake picklable report")
