# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import TestCase

from click.testing import CliRunner

from fixit import __version__
from fixit.cli import main


class SmokeTest(TestCase):
    def setUp(self):
        self.runner = CliRunner(mix_stderr=False)

    def test_cli_version(self):
        result = self.runner.invoke(main, ["--version"])
        expected = rf"fixit, version {__version__}"
        self.assertIn(expected, result.stdout)

    def test_this_file_is_clean(self) -> None:
        path = Path(__file__).resolve().as_posix()
        result = self.runner.invoke(main, ["lint", path], catch_exceptions=False)
        self.assertEqual(result.output, "")
        self.assertEqual(result.exit_code, 0)

    def test_this_project_is_clean(self) -> None:
        project_dir = Path(__file__).resolve().parent.parent.as_posix()
        result = self.runner.invoke(main, ["lint", project_dir], catch_exceptions=False)
        self.assertEqual(result.output, "")
        self.assertEqual(result.exit_code, 0)

    def test_directory_with_violations(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            (tdp / "clean.py").write_text("name = 'Kirby'\nprint(f'hello {name}')")
            (tdp / "dirty.py").write_text("name = 'Kirby'\nprint('hello %s' % name)\n")

            result = self.runner.invoke(main, ["lint", td])
            self.assertIn("dirty.py@2:6 UseFstringRule:", result.output)
            self.assertEqual(result.exit_code, 1)

    def test_directory_with_errors(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            (tdp / "clean.py").write_text("name = 'Kirby'\nprint(f'hello {name}')")
            (tdp / "broken.py").write_text("print)\n")

            result = self.runner.invoke(main, ["lint", td])
            self.assertIn("broken.py: EXCEPTION: Syntax Error @ 1:", result.output)
            self.assertEqual(result.exit_code, 2)

    def test_directory_with_violations_and_errors(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            (tdp / "clean.py").write_text("name = 'Kirby'\nprint(f'hello {name}')")
            (tdp / "dirty.py").write_text("name = 'Kirby'\nprint('hello %s' % name)\n")
            (tdp / "broken.py").write_text("print)\n")

            result = self.runner.invoke(main, ["lint", td])
            self.assertIn("dirty.py@2:6 UseFstringRule:", result.output)
            self.assertIn("broken.py: EXCEPTION: Syntax Error @ 1:", result.output)
            self.assertEqual(result.exit_code, 3)

    def test_directory_with_autofixes(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td).resolve()
            clean = tdp / "clean.py"
            clean.write_text(
                dedent(
                    """
                    GLOBAL = 'hello'

                    def foo():
                        value = 'test'
                        if value is False:
                            pass
                    """
                )
            )
            single = tdp / "single.py"
            single.write_text(
                dedent(
                    """
                    GLOBAL = f'hello'

                    def foo():
                        value = 'test'
                        if value is False:
                            pass
                    """
                )
            )
            multi = tdp / "multi.py"
            multi.write_text(
                dedent(
                    """
                    GLOBAL = f'hello'

                    def foo():
                        value = f'test'
                        if value == False:
                            pass
                    """
                )
            )

            expected = clean.read_text()

            result = self.runner.invoke(main, ["fix", "--automatic", td])
            errors = defaultdict(list)
            for line in result.output.splitlines():
                fn, _, error = line.partition("@")
                short, _, _ = error.partition(": ")
                errors[Path(fn)].append(short)

            with self.subTest("clean"):
                self.assertListEqual([], errors[clean])
                self.assertEqual(expected, clean.read_text())

            with self.subTest("single fix"):
                self.assertListEqual(
                    [
                        "2:9 NoRedundantFStringRule",
                    ],
                    sorted(errors[single]),
                )
                self.assertEqual(expected, single.read_text())

            with self.subTest("multiple fixes"):
                self.assertListEqual(
                    [
                        "2:9 NoRedundantFStringRule",
                        "5:12 NoRedundantFStringRule",
                        "6:7 CompareSingletonPrimitivesByIsRule",
                    ],
                    sorted(errors[multi]),
                )
                self.assertEqual(expected, multi.read_text())
