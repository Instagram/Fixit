# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import copy
import re
import textwrap
import unittest
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from libcst.testing.utils import data_provider
from mypy_extensions import TypedDict

from fixit.common.base import CstLintRule
from fixit.common.report import BaseLintRuleReport
from fixit.common.utils import InvalidTestCase, ValidTestCase  # noqa: F401
from fixit.rule_lint_engine import get_rules, lint_file


@dataclass(frozen=True)
class TestCase:
    rule: Type[CstLintRule]
    test_methods: Mapping[str, Union[ValidTestCase, InvalidTestCase]]


class BaseTestMeta(type):
    def __new__(cls, name: str, bases: Tuple[type, ...], dct: Dict[str, Any]) -> object:
        test_cases: Sequence[TestCase] = cls._gen_test_cases()
        cls.populate_data_provider_tests(dct, test_cases)
        return super().__new__(cls, name, bases, dict(dct))

    @classmethod
    def populate_data_provider_tests(cls, dct, test_cases: Sequence[TestCase]) -> None:
        test_cases_to_add: Dict[str, unittest.TestCase] = {}
        for test_case in test_cases:
            rule_name = test_case.rule.__name__
            test_methods_to_add: Dict[str, Callable] = dict()

            for test_method_name, test_method_data in test_case.test_methods.items():
                # member = dct["_test_case"]

                # @wraps(member)
                def test_method(
                    self: object,
                    data: Union[ValidTestCase, InvalidTestCase] = test_method_data,
                    rule: Type[CstLintRule] = test_case.rule,
                ) -> object:
                    return self._test_case(data, rule)

                test_method.__name__ = test_method_name
                test_methods_to_add[test_method_name] = test_method

            test_case_type = type(
                rule_name, (LintRuleTestCaseStub,), test_methods_to_add
            )
            test_cases_to_add.update({rule_name: test_case_type})
        dct.update(test_cases_to_add)

    @classmethod
    def _gen_test_cases(cls) -> Sequence[TestCase]:
        cases = []
        for rule in get_rules():
            if not issubclass(rule, CstLintRule):
                continue
            test_cases_for_rule = cls._gen_test_case(rule)
            cases.append(test_cases_for_rule)
        return cases

    @classmethod
    def _gen_test_case(cls, rule) -> TestCase:
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
        return TestCase(rule=rule, test_methods={**valid_tcs, **invalid_tcs})


class LintRuleTestCaseStub(unittest.TestCase):
    @staticmethod
    def _dedent(src: str) -> str:
        src = re.sub(r"\A\n", "", src)
        return textwrap.dedent(src)

    @staticmethod
    def _validate_patch(
        report: BaseLintRuleReport, test_case: InvalidTestCase
    ) -> unittest.TestResult:
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

    def _test_case(
        self, test_case: Union[ValidTestCase, InvalidTestCase], rule: Type[CstLintRule],
    ) -> None:
        reports = lint_file(
            Path(test_case.filename),
            LintRuleTestCaseStub._dedent(test_case.code).encode("utf-8"),
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

            LintRuleTestCaseStub._validate_patch(report, test_case)


class TestLintRules(unittest.TestSuite, metaclass=BaseTestMeta):
    pass
