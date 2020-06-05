# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping, Sequence, Type, Union

from fixit.common.base import CstLintRule
from fixit.common.testing import LintRuleTest
from fixit.common.utils import InvalidTestCase, ValidTestCase  # noqa: F401
from fixit.rule_lint_engine import get_rules, lint_file


@dataclass(frozen=True)
class TestCasePrecursor:
    rule: Type[CstLintRule]
    test_methods: Mapping[str, Union[ValidTestCase, InvalidTestCase]]


def _gen_test_methods_for_rule(rule: Type[CstLintRule]) -> TestCasePrecursor:
    """ Aggregates all of the cases inside a single CstLintRule's VALID and INVALID attributes
    and maps them to altered names with a `test_` prefix so that 'unittest' can discover them
    later on and an index postfix so that individual tests can be selected from the command line.
    """
    valid_tcs = dict()
    invalid_tcs = dict()
    if issubclass(rule, CstLintRule):

        if hasattr(rule, "VALID"):
            # pyre-ignore[16]: `CstLintRule` has no attribute `VALID`.
            for idx, test_case in enumerate(rule.VALID):
                valid_tcs[f"test_VALID_{idx}"] = test_case
        if hasattr(rule, "INVALID"):
            # pyre-ignore[16]: `CstLintRule` has no attribute `INVALID`.
            for idx, test_case in enumerate(rule.INVALID):
                invalid_tcs[f"test_INVALID_{idx}"] = test_case
    return TestCasePrecursor(rule=rule, test_methods={**valid_tcs, **invalid_tcs})


def _gen_all_test_methods() -> Sequence[TestCasePrecursor]:
    """
    Converts all discoverable lint rules to type `TestCasePrecursor` to ease further TestCase
    creation later on.
    """
    cases = []
    for rule in get_rules():
        if not issubclass(rule, CstLintRule):
            continue
        # pyre-ignore[6]: Expected `Type[CstLintRule]` for 1st anonymous parameter to call
        # `_gen_test_methods_for_rule` but got `Union[Type[CstLintRule], Type[PseudoLintRule]]`.
        test_cases_for_rule = _gen_test_methods_for_rule(rule)
        cases.append(test_cases_for_rule)
    return cases


def add_lint_rule_tests_to_module() -> None:
    """
    Creates LintRuleTestCase types from CstLintRule types and adds them to module's attributes
    in order to be discoverable by 'unittest'.
    """
    for test_case in _gen_all_test_methods():
        rule_name = test_case.rule.__name__
        test_methods_to_add: Dict[str, Callable] = dict()

        for test_method_name, test_method_data in test_case.test_methods.items():

            def test_method(
                self: Type[LintRuleTestCase],
                data: Union[ValidTestCase, InvalidTestCase] = test_method_data,
                rule: Type[CstLintRule] = test_case.rule,
            ) -> None:
                return self._test_method(data, rule)

            test_method.__name__ = test_method_name
            test_methods_to_add[test_method_name] = test_method

        test_case_class = type(rule_name, (LintRuleTestCase,), test_methods_to_add)
        globals()[rule_name] = test_case_class


class LintRuleTestCase(unittest.TestCase):
    def _test_method(
        self, test_case: Union[ValidTestCase, InvalidTestCase], rule: Type[CstLintRule],
    ) -> None:
        reports = lint_file(
            Path(test_case.filename),
            LintRuleTest.dedent(test_case.code).encode("utf-8"),
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


add_lint_rule_tests_to_module()
