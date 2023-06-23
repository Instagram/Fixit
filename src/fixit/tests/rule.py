# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path
from textwrap import dedent
from unittest import TestCase
from unittest.mock import MagicMock

import libcst as cst
from libcst.metadata import CodePosition, CodeRange

from ..engine import LintRunner
from ..ftypes import Config, LintViolation
from ..rule import LintRule


class NoopRule(LintRule):
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
        self.runner = LintRunner(Path("fake.py"), b"pass")

    def test_no_rules(self) -> None:
        violations = self.runner.collect_violations([], Config())
        self.assertEqual(list(violations), [])

    def test_noop_rule(self) -> None:
        rule = NoopRule()
        violations = self.runner.collect_violations([rule], Config())
        self.assertEqual(list(violations), [])
        self.assertTrue(rule.called)

    def test_timing(self) -> None:
        rule = NoopRule()
        for _ in self.runner.collect_violations([rule], Config()):
            pass  # exhaust the generator
        self.assertIn("NoopRule.visit_Module", self.runner.timings)
        self.assertIn("NoopRule.leave_Module", self.runner.timings)
        self.assertGreaterEqual(self.runner.timings["NoopRule.visit_Module"], 0)

    def test_timing_hook(self) -> None:
        rule = NoopRule()
        hook = MagicMock()
        for i, _ in enumerate(
            self.runner.collect_violations([rule], Config(), timings_hook=hook)
        ):
            if i <= 1:
                # only called at the end
                hook.assert_not_called()
        hook.assert_called_once()


class ExerciseReportRule(LintRule):
    MESSAGE = "message on the class"

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self.report(node, "class def")
        return False

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
        self.rules = [ExerciseReportRule()]

    def test_pass_happy(self) -> None:
        runner = LintRunner(Path("fake.py"), b"pass")
        (violation,) = list(runner.collect_violations(self.rules, Config()))
        self.assertIsInstance(violation.node, cst.Pass)
        self.assertEqual(
            violation,
            LintViolation(
                "ExerciseReport",
                CodeRange(start=CodePosition(1, 0), end=CodePosition(1, 4)),
                "I pass",
                violation.node,
                None,
            ),
        )

    def test_ellipsis_position_override(self) -> None:
        runner = LintRunner(Path("fake.py"), b"...")
        (violation,) = list(runner.collect_violations(self.rules, Config()))
        self.assertIsInstance(violation.node, cst.Ellipsis)
        self.assertEqual(
            violation,
            LintViolation(
                "ExerciseReport",
                CodeRange(start=CodePosition(1, 1), end=CodePosition(2, 0)),
                "I ellipse",
                violation.node,
                None,
            ),
        )

    def test_del_no_message(self) -> None:
        runner = LintRunner(Path("fake.py"), b"del foo")
        violations = list(runner.collect_violations(self.rules, Config()))
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].message, "message on the class")

    def test_ignore_lint(self) -> None:
        idx = 0
        for code, message, position in (
            ("pass  # random comment\n", "I pass", (1, 0)),
            ("pass\n", "I pass", (1, 0)),
            ("pass  # lint-fixme\n", None, None),
            ("pass  # lint-ignore\n", None, None),
            ("pass  # lint-fixme: ExerciseReport\n", None, None),
            ("pass  # lint-ignore: ExerciseReport\n", None, None),
            ("pass  # lint-fixme: SomethingElse, ExerciseReport\n", None, None),
            ("pass  # lint-ignore: SomethingElse, ExerciseReport\n", None, None),
            ("pass  # lint-fixme: SomethingElse\n", "I pass", (1, 0)),
            ("pass  # lint-ignore: SomethingElse\n", "I pass", (1, 0)),
            ("# random comment\npass\n", "I pass", (2, 0)),
            ("# lint-fixme\npass\n", None, None),
            ("# lint-ignore\npass\n", None, None),
            ("# lint-fixme: ExerciseReport\npass\n", None, None),
            ("# lint-ignore: ExerciseReport\npass\n", None, None),
            ("# lint-fixme: SomethingElse, ExerciseReport\npass\n", None, None),
            ("# lint-ignore: SomethingElse, ExerciseReport\npass\n", None, None),
            ("# lint-fixme: SomethingElse\npass\n", "I pass", (2, 0)),
            ("# lint-ignore: SomethingElse\npass\n", "I pass", (2, 0)),
            ("def foo(bar): pass\n", "I pass", (1, 14)),
            ("def foo(bar): pass  # lint-ignore\n", None, None),
            ("# lint-ignore\ndef foo(bar): pass\n", None, None),
            ("import sys\n# lint-ignore\ndef foo(bar): pass\n", None, None),
            ("class bar(object): value = 1\n", "class def", (1, 0)),
            ("class bar(object): value = 1  # lint-fixme\n", None, None),
            ("# lint-fixme\nclass bar(object): value = 1\n", None, None),
            ("import sys\n# lint-fixme\nclass bar(object): value = 1\n", None, None),
            (
                """
                    import sys

                    class Foo(object):
                        value = 1
                """,
                "class def",
                (4, 0),
            ),
            (
                """
                    import sys

                    class Foo(object):  # comment
                        value = 1
                """,
                "class def",
                (4, 0),
            ),
            (
                """
                    import sys

                    class Foo(object):  # lint-ignore
                        value = 1
                """,
                None,
                None,
            ),
            (
                """
                    import sys

                    class Foo(object):  # lint-ignore ExerciseReport
                        value = 1
                """,
                None,
                None,
            ),
            (
                """
                    import sys

                    # lint-fixme
                    class Foo(object):
                        value = 1
                """,
                None,
                None,
            ),
            (
                """
                    import sys

                    # lint-fixme: UnrelatedRule
                    class Foo(object):
                        value = 1
                """,
                "class def",
                (5, 0),
            ),
        ):
            idx += 1
            content = dedent(code).encode("utf-8")
            with self.subTest(f"code {idx}"):
                runner = LintRunner(Path("fake.py"), content)
                violations = list(
                    runner.collect_violations([ExerciseReportRule()], Config())
                )

                if message and position:
                    self.assertEqual(len(violations), 1)
                    (violation,) = violations
                    self.assertEqual(violation.message, message)
                    self.assertEqual(violation.range.start, CodePosition(*position))

                else:
                    self.assertListEqual([], violations)
