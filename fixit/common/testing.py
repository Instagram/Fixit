# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
import textwrap
from typing import Iterable, Optional, Tuple, Type, Union, Any

from libcst.testing.utils import (  # noqa IG69: this module is only used by tests
    UnitTest,
)

from fixit import rule_lint_engine
from fixit.common.base import CstLintRule
from fixit.common.config import REPO_ROOT
from fixit.common.report import BaseLintRuleReport
from fixit.common.utils import InvalidTestCase, ValidTestCase


def _dedent(src: str) -> str:
    src = re.sub(r"\A\n", "", src)
    return textwrap.dedent(src)

def data_provider_DEPRECATED(fn_data_provider):
    """
    NOTE: This data provider method is deprecated in favor of a newer version.  Please
    use that one instead.

    Data provider decorator, allows another callable to provide the data for the testself.
    """
    def test_decorator(fn):
        def repl(self, *args) -> None:
            provided_data = fn_data_provider(self)
            for data_idx, data_entry in enumerate(provided_data):
                if isinstance(provided_data, dict):
                    func_args = provided_data[data_entry]
                    dataset_name = f"'{data_entry}'"
                else:
                    func_args = data_entry
                    dataset_name = str(data_idx)
                # Set the index of the current iteration on the test class itself and clean it
                # up afterwards.  This allows the test to figure out which test case it's currently
                # processing.
                self._data_provider_index = data_idx
                try:
                    if isinstance(func_args, dict):
                        fn(self, **func_args)
                    else:
                        fn(self, *func_args)
                except Exception:
                    print()
                    print(f"Exception caught with data set {dataset_name}:", func_args)
                    raise
            try:
                delattr(self, "_data_provider_index")
            except AttributeError:
                pass

        async def async_repl(self, *args) -> None:
            provided_data = fn_data_provider(self)
            for data_idx, data_entry in enumerate(provided_data):
                if isinstance(provided_data, dict):
                    func_args = provided_data[data_entry]
                    dataset_name = f"'{data_entry}'"
                else:
                    func_args = data_entry
                    dataset_name = str(data_idx)
                # Set the index of the current iteration on the test class itself and clean it
                # up afterwards.  This allows the test to figure out which test case it's currently
                # processing.
                self._data_provider_index = data_idx
                try:
                    if isinstance(func_args, dict):
                        fn(self, **func_args)
                    else:
                        fn(self, *func_args)
                except Exception:
                    print()
                    print(f"Exception caught with data set {dataset_name}:", func_args)
                    raise
            try:
                delattr(self, "_data_provider_index")
            except AttributeError:
                pass

        return repl

    return test_decorator



# We can't use an ABCMeta here, because of metaclass conflicts
# pyre-fixme[13]: Attribute `VALID` is never initialized.
class LintRuleTest(UnitTest):
    ONCALL_SHORTNAME = "instagram_server_framework"

    RULE: Type[CstLintRule]
    VALID: Iterable[ValidTestCase]
    INVALID: Iterable[InvalidTestCase]

    def _test_rule_in_list(self, rule: Type[CstLintRule]) -> None:
        if type(self) is not LintRuleTest:
            self.assertIn(
                rule,
                rule_lint_engine.RULES,
                "rule must be in static_analysis.lint.rule_lint_engine.RULES",
            )

    def __test_case_data_provider(
        self,
    ) -> Iterable[Tuple[Union[ValidTestCase, InvalidTestCase]]]:
        # don't execute this test for the base class
        if type(self) is not LintRuleTest:
            for vtc in self.VALID:
                yield (vtc,)
            for itc in self.INVALID:
                yield (itc,)

    def validate_patch(
        self, report: BaseLintRuleReport, test_case: InvalidTestCase
    ) -> None:
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

    @data_provider_DEPRECATED(__test_case_data_provider)
    def test_rule(self, test_case: Union[ValidTestCase, InvalidTestCase]) -> None:
        self._test_rule(test_case)

    def _test_rule(
        self,
        test_case: Union[ValidTestCase, InvalidTestCase],
        rule: Optional[Type[CstLintRule]] = None,
    ) -> None:
        rule = self.RULE if rule is None else rule
        self._test_rule_in_list(rule)
        reports = rule_lint_engine.lint_file(
            REPO_ROOT / test_case.filename,
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

            self.validate_patch(report, test_case)
