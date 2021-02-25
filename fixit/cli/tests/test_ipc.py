# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import contextlib
import io
import json
import tempfile

from libcst.testing.utils import UnitTest

from fixit.cli import run_ipc
from fixit.cli.args import LintWorkers
from fixit.cli.tests.test_lint_opts import generate_mock_lint_opt


TARGET_PATH = None
EXPECTED_SUCCESS_REPORT = json.loads(
    """{"path": "fill-this-out", "status": "success", "reports": ["fake picklable report"]}"""
)
EXPECTED_FAILURE_REPORT = json.loads(
    """{"path": "fill-this-out", "status": "failure", "reports": ["fake picklable report"]}"""
)


class IpcTest(UnitTest):
    def setUp(self) -> None:
        self.opts = generate_mock_lint_opt()

    def test_single_path_ipc(self) -> None:
        with io.StringIO() as buffer, tempfile.NamedTemporaryFile(
            "w+"
        ) as fd, contextlib.redirect_stdout(buffer):
            # create a valid file for the test to run against
            fd.write("""test_str = 'hello world'""")
            fd.flush()
            path = fd.name

            run_ipc(
                opts=self.opts, paths=[path], workers=LintWorkers.USE_CURRENT_THREAD
            )

            # get values from the buffer before we close it
            buffer.flush()
            output = buffer.getvalue()

        report = json.loads(output)

        target_report = EXPECTED_SUCCESS_REPORT.copy()
        target_report["path"] = path

        self.assertDictEqual(report, target_report)

    def test_multi_path_ipc(self) -> None:
        with io.StringIO() as buffer, tempfile.NamedTemporaryFile(
            "w+"
        ) as fd_a, tempfile.NamedTemporaryFile(
            "w+"
        ) as fd_b, contextlib.redirect_stdout(
            buffer
        ):
            # create a valid file for the test to run against
            fd_a.write("""test_str = 'hello world'""")
            fd_a.flush()

            # now create an invalid one
            # mismatched tab-indent will do the trick
            fd_b.write("""\ta = 1\nb = 2""")
            fd_b.flush()
            path_a = fd_a.name
            path_b = fd_b.name

            # this path doesn't exist at all, but the runner should still handle it gracefully
            path_c = "/does/not/exist.tmp"

            run_ipc(
                opts=self.opts,
                paths=[path_a, path_b, path_c],
                workers=LintWorkers.USE_CURRENT_THREAD,
            )

            # get values from the buffer before we close it
            buffer.flush()
            output = buffer.getvalue()

        # each report is separated by a new-line
        reports = output.strip().split("\n")
        print("split", reports)
        self.assertEqual(len(reports), 3)
        report_a, report_b, report_c = [json.loads(report) for report in reports]

        target_report_a = EXPECTED_SUCCESS_REPORT.copy()
        target_report_a["path"] = path_a

        target_report_b = EXPECTED_FAILURE_REPORT.copy()
        target_report_b["path"] = path_b

        target_report_c = EXPECTED_FAILURE_REPORT.copy()
        target_report_c["path"] = path_c

        self.assertDictEqual(report_a, target_report_a)
        self.assertDictEqual(report_b, target_report_b)
        self.assertDictEqual(report_c, target_report_c)
