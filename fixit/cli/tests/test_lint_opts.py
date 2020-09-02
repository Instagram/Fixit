# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass
from pathlib import Path
from typing import Collection, List, Sequence, cast

from libcst import Module
from libcst.testing.utils import UnitTest

from fixit.cli import LintOpts, map_paths
from fixit.cli.args import LintWorkers
from fixit.common.base import CstLintRule, LintConfig
from fixit.common.report import (
    BaseLintRuleReport,
    LintFailureReportBase,
    LintSuccessReportBase,
)
from fixit.rule_lint_engine import lint_file


@dataclass(frozen=True)
class FakeLintSuccessReport(LintSuccessReportBase):
    path: str
    status: str
    reports: Collection[str]

    @staticmethod
    def create_reports(
        path: Path, reports: Collection[BaseLintRuleReport], global_list: List[str],
    ) -> Sequence["FakeLintSuccessReport"]:
        global_list.append(str(path))
        return [FakeLintSuccessReport(str(path), "success", ["fake picklable report"])]


class FakeRule(CstLintRule):
    def visit_Module(self, node: Module) -> None:
        self.report(node, "Dummy message")


def mock_operation(
    path: Path, opts: LintOpts, _=None,
) -> Sequence[FakeLintSuccessReport]:
    results = opts.success_report.create_reports(
        path,
        lint_file(path, b"test", rules=opts.rules, config=LintConfig()),
        **opts.extra,
    )
    return cast(Sequence[FakeLintSuccessReport], results)


class LintOptsTest(UnitTest):
    def setUp(self) -> None:
        self.global_list = []
        self.opts = LintOpts(
            {FakeRule},
            FakeLintSuccessReport,
            LintFailureReportBase,
            extra={"global_list": self.global_list},
        )

    def test_extra_opts(self) -> None:
        path = "path.py"
        results = next(
            map_paths(
                mock_operation,
                [path],
                self.opts,
                workers=LintWorkers.USE_CURRENT_THREAD,
            )
        )

        # Assert global list has been modified as expected.
        self.assertEqual(list(self.global_list), [path])

        # Assert the rest of the reporting functionality is as expected
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].reports, ["fake picklable report"])

    def test_extra_opts_multiple_paths(self) -> None:
        paths = ["path1.py", "path2.py"]
        results_iter = map_paths(
            mock_operation, paths, self.opts, workers=LintWorkers.USE_CURRENT_THREAD
        )
        results_count = 0
        paths_reported = []
        for results in results_iter:
            for result in results:
                results_count += 1
                paths_reported.append(result.path)
                self.assertEqual(len(result.reports), 1)
                self.assertEqual(result.reports, ["fake picklable report"])

        # Assert global list has been modified as expected.
        self.assertCountEqual(list(self.global_list), paths)

        # Assert all passed in paths have been visited as expected
        self.assertCountEqual(paths_reported, paths)
