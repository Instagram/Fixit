# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from unittest import TestCase
from unittest.mock import MagicMock

import libcst as cst
from libcst.metadata import CodePosition, CodeRange

from fixit.ftypes import LintViolation

from fixit.rule.cst import CSTLintRule, CSTLintRunner


class NoopRule(CSTLintRule):
    def __init__(self) -> None:
        super().__init__()
        self.called = False

    def visit_Module(self, node: cst.Module) -> bool:
        self.called = True
        return False

    def leave_Module(self, original_node: cst.Module) -> None:
        pass


class RunnerTest(TestCase):
    def setUp(self) -> None:
        self.runner = CSTLintRunner()

    def test_no_rules(self) -> None:
        violations = self.runner.collect_violations(b"pass", [])
        self.assertEqual(list(violations), [])

    def test_noop_rule(self) -> None:
        rule = NoopRule()
        violations = self.runner.collect_violations(b"pass", [rule])
        self.assertEqual(list(violations), [])
        self.assertTrue(rule.called)

    def test_timing(self) -> None:
        rule = NoopRule()
        for _ in self.runner.collect_violations(b"pass", [rule]):
            pass  # exhaust the generator
        self.assertIn("NoopRule.visit_Module", self.runner.timings)
        self.assertIn("NoopRule.leave_Module", self.runner.timings)
        self.assertGreaterEqual(self.runner.timings["NoopRule.visit_Module"], 0)

    def test_timing_hook(self) -> None:
        rule = NoopRule()
        hook = MagicMock()
        for i, _ in enumerate(
            self.runner.collect_violations(b"pass", [rule], timings_hook=hook)
        ):
            if i <= 1:
                # only called at the end
                hook.assert_not_called()
        hook.assert_called_once()


class ExerciseReportRule(CSTLintRule):
    MESSAGE = "message on the class"

    def visit_Pass(self, node: cst.Pass) -> bool:
        self.report(node, "I pass")
        return False

    def visit_Ellipsis(self, node: cst.Ellipsis) -> bool:
        self.report(node, "I ellipse", position=CodePosition(line=1, column=1))
        return False

    def visit_Del(self, node: cst.Del) -> bool:
        self.report(node)
        return False


class RuleTest(TestCase):
    def setUp(self) -> None:
        self.runner = CSTLintRunner()
        self.rules = [ExerciseReportRule()]

    def test_pass_happy(self) -> None:
        violations = list(self.runner.collect_violations(b"pass", self.rules))
        self.assertEqual(
            violations,
            [
                LintViolation(
                    "ExerciseReportRule",
                    CodeRange(start=CodePosition(1, 0), end=CodePosition(1, 4)),
                    "I pass",
                    False,
                )
            ],
        )

    def test_ellipsis_position_override(self) -> None:
        violations = list(self.runner.collect_violations(b"...", self.rules))
        self.assertEqual(
            violations,
            [
                LintViolation(
                    "ExerciseReportRule",
                    CodeRange(start=CodePosition(1, 1), end=CodePosition(2, 0)),
                    "I ellipse",
                    False,
                )
            ],
        )

    def test_del_no_message(self) -> None:
        violations = list(self.runner.collect_violations(b"del foo", self.rules))
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].message, "message on the class")
