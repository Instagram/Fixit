# Copyright (c) Meta Platforms, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from unittest import TestCase
from unittest.mock import MagicMock

import libcst as cst

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
