# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
import textwrap
from pathlib import Path
from typing import Iterable, Optional, Type, Union

from libcst.testing.utils import (  # noqa IG69: this module is only used by tests
    UnitTest,
)

from fixit import rule_lint_engine
from fixit.common.base import CstLintRule
from fixit.common.report import BaseLintRuleReport
from fixit.common.utils import InvalidTestCase, ValidTestCase


def _dedent(src: str) -> str:
    src = re.sub(r"\A\n", "", src)
    return textwrap.dedent(src)


# We can't use an ABCMeta here, because of metaclass conflicts
# pyre-fixme[13]: Attribute `VALID` is never initialized.
class LintRuleTest(UnitTest):
    RULE: Type[CstLintRule]
    VALID: Iterable[ValidTestCase]
    INVALID: Iterable[InvalidTestCase]

    def _test_rule_in_list(self, rule: Type[CstLintRule]) -> None:
        if type(self) is not LintRuleTest:
            self.assertIn(
                rule,
                rule_lint_engine.get_rules(),
                "rule must be in fixit.rule_lint_engine.get_rules()",
            )

    @staticmethod
    def validate_patch(report: BaseLintRuleReport, test_case: InvalidTestCase) -> None:
        patch = report.patch
        expected_replacement = test_case.expected_replacement

        if patch is None:
            if expected_replacement is not None:
                raise AssertionError(
                    "The rule for this test case has no auto-fix, but expected source was specified."
                )
            return

        if expected_replacement is None:
            raise AssertionError(
                "The rule for this test case has an auto-fix, but no expected source was specified."
            )

        expected_replacement = _dedent(expected_replacement)
        patched_code = patch.apply(_dedent(test_case.code))
        if patched_code != expected_replacement:
            raise AssertionError(
                "Auto-fix did not produce expected result.\n"
                + f"Expected:\n{expected_replacement}\n"
                + f"But found:\n{patched_code}"
            )

    def _test_rule(
        self,
        test_case: Union[ValidTestCase, InvalidTestCase],
        rule: Optional[Type[CstLintRule]] = None,
    ) -> None:
        rule = self.RULE if rule is None else rule
        self._test_rule_in_list(rule)
        reports = rule_lint_engine.lint_file(
            Path(test_case.filename),
            _dedent(test_case.code).encode("utf-8"),
            config=test_case.config,
            rules=[rule],
        )
        if isinstance(test_case, ValidTestCase):
            self.assertEqual(
                len(reports),
                0,
                'Expected zero reports for this "valid" test case. Instead, found:\n'
                + "\n".join(str(e) for e in reports),
            )
        else:
            self.assertGreater(
                len(reports),
                0,
                'Expected a report for this "invalid" test case. `self.report` was not called.',
            )
            self.assertLessEqual(
                len(reports),
                1,
                'Expected one report from this "invalid" test case. Found multiple:\n'
                + "\n".join(str(e) for e in reports),
            )

            # pyre-fixme[16]: `Collection` has no attribute `__getitem__`.
            report = reports[0]

            if not (test_case.line is None or test_case.line == report.line):
                raise AssertionError(
                    f"Expected line: {test_case.line} but found line: {report.line}"
                )

            if not (test_case.column is None or test_case.column == report.column):
                raise AssertionError(
                    f"Expected column: {test_case.column} but found column: {test_case.column}"
                )

            if test_case.kind != report.code:
                raise AssertionError(
                    f"Expected:\n    {test_case.expected_str}\nBut found:\n    {report}"
                )

            LintRuleTest.validate_patch(report, test_case)
