# Copyright (c) Meta Platforms, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from unittest import TestCase

from click.testing import CliRunner

from fixit import __version__
from fixit.cli import main


class SmokeTest(TestCase):
    def setUp(self):
        self.runner = CliRunner(mix_stderr=False)

    def test_cli_version(self):
        result = self.runner.invoke(main, ["--version"])
        self.assertRegex(result.stdout, rf"fixit, version {__version__}")

    def test_this_file_is_clean(self) -> None:
        result = self.runner.invoke(main, ["lint", __file__])
        self.assertEqual(result.output, "")
        self.assertEqual(result.exit_code, 0)
