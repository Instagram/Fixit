# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import contextlib
import io
import json
import os
import tempfile
from typing import Any, Dict

from libcst.testing.utils import UnitTest

from fixit.cli import run_ipc
from fixit.cli.args import LintWorkers
from fixit.cli.tests.test_lint_opts import generate_mock_lint_opt


EXPECTED_SUCCESS_REPORT: Dict[str, Any] = json.loads(
    """{"path": "fill-this-out", "status": "success", "reports": ["fake picklable report"]}"""
)
EXPECTED_FAILURE_REPORT: Dict[str, Any] = json.loads(
    """{"path": "fill-this-out", "status": "failure", "reports": ["fake picklable report"]}"""
)


class IpcTest(UnitTest):
    def setUp(self) -> None:
        self.opts = generate_mock_lint_opt()

    def test_single_path_ipc(self) -> None:
        with io.StringIO() as buffer, tempfile.TemporaryDirectory() as prefix, contextlib.redirect_stdout(
            buffer
        ):
            # create a valid file for the test to run against
            path = "path.py"

            with open(os.path.join(prefix, path), "w") as fd:
                fd.write("""test_str = 'hello world'""")

            run_ipc(
                opts=self.opts,
                paths=[path],
                prefix=prefix,
                workers=LintWorkers.USE_CURRENT_THREAD,
            )

            # get values from the buffer before we close it
            buffer.flush()
            output = buffer.getvalue()

        report = json.loads(output)

        target_report = EXPECTED_SUCCESS_REPORT.copy()
        target_report["path"] = os.path.join(prefix, path)

        self.assertDictEqual(report, target_report)

    def test_multi_path_ipc(self) -> None:
        with io.StringIO() as buffer, tempfile.TemporaryDirectory() as prefix, contextlib.redirect_stdout(
            buffer
        ):
            path_a = "path_a.py"
            path_b = "path_b.py"
            # this path doesn't exist at all, but the runner should still handle it gracefully
            path_c = "does_not_exist.tmp"

            # create a valid file for the test to run against
            with open(os.path.join(prefix, path_a), "w") as fd_a:
                fd_a.write("""test_str = 'hello world'""")

            # now create an invalid one
            # mismatched tab-indent will do the trick
            with open(os.path.join(prefix, path_b), "w") as fd_b:
                fd_b.write("""\ta = 1\nb = 2""")

            run_ipc(
                opts=self.opts,
                paths=[path_a, path_b, path_c],
                prefix=prefix,
                workers=LintWorkers.USE_CURRENT_THREAD,
            )

            # get values from the buffer before we close it
            buffer.flush()
            output = buffer.getvalue()

        # each report is separated by a new-line
        reports = output.strip().split("\n")
        self.assertEqual(len(reports), 3)
        report_a, report_b, report_c = [json.loads(report) for report in reports]

        target_report_a = EXPECTED_SUCCESS_REPORT.copy()
        target_report_a["path"] = os.path.join(prefix, path_a)

        target_report_b = EXPECTED_FAILURE_REPORT.copy()
        target_report_b["path"] = os.path.join(prefix, path_b)

        target_report_c = EXPECTED_FAILURE_REPORT.copy()
        target_report_c["path"] = os.path.join(prefix, path_c)

        self.assertDictEqual(report_a, target_report_a)
        self.assertDictEqual(report_b, target_report_b)
        self.assertDictEqual(report_c, target_report_c)
