# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from pathlib import Path

from fixit.common.base import LintConfig
from fixit.common.pseudo_rule import PseudoContext
from fixit.rule_lint_engine import lint_file
from fixit.rules.flake8_compat import Flake8PseudoLintRule


class Flake8PseudoLintRuleTest(unittest.TestCase):
    def test_lint_file(self) -> None:
        context = PseudoContext(
            file_path=Path("dummy/file/path.py"), source=b"undefined_fn()\n"
        )
        rule = Flake8PseudoLintRule(context)
        results = list(rule.lint_file())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "F821")  # undefined name

    def test_flake8_noqa_is_disabled(self) -> None:
        context = PseudoContext(
            file_path=Path("dummy/file/path.py"), source=b"undefined_fn()  # noqa\n"
        )
        rule = Flake8PseudoLintRule(context)
        results = list(rule.lint_file())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "F821")  # undefined name

    def test_lint_file_with_framework(self) -> None:
        results = list(
            lint_file(
                file_path=Path("dummy/file/path.py"),
                source=b"undefined_fn()\n",
                rules={Flake8PseudoLintRule},
                config=LintConfig(),
            )
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "F821")  # undefined name

    def test_lint_ignore_with_framework(self) -> None:
        results = list(
            lint_file(
                file_path=Path("dummy/file/path.py"),
                source=b"# lint-ignore: F821: testing ignores\nundefined_fn()\n",
                rules={Flake8PseudoLintRule},
                config=LintConfig(),
            )
        )
        self.assertEqual(results, [])
