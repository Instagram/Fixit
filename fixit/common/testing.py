# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Type, Union, cast

from libcst.metadata import MetadataWrapper
from libcst.testing.utils import (  # noqa IG69: this module is only used by tests
    UnitTest,
)

from fixit.common.base import CstLintRule
from fixit.common.report import BaseLintRuleReport
from fixit.common.utils import (
    InvalidTestCase,
    InvalidTypeDependentTestCase,
    ValidTestCase,
    ValidTypeDependentTestCase,
    _dedent,
)
from fixit.rule_lint_engine import LintRuleCollectionT, lint_file


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


@dataclass(frozen=True)
class TestCasePrecursor:
    rule: Type[CstLintRule]
    test_methods: Mapping[
        str, Union[ValidTestCase, InvalidTestCase],
    ]


class LintRuleTestCase(unittest.TestCase):
    def _test_method(
        self,
        test_case: Union[ValidTestCase, InvalidTestCase],
        rule: Type[CstLintRule],
        metadata_wrapper: Optional[MetadataWrapper] = None,
    ) -> None:
        reports = lint_file(
            Path(test_case.filename),
            _dedent(test_case.code).encode("utf-8"),
            config=test_case.config,
            rules=[rule],
            cst_wrapper=metadata_wrapper,
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

            validate_patch(report, test_case)


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


def _gen_all_test_methods(rules: LintRuleCollectionT) -> Sequence[TestCasePrecursor]:
    """
    Converts all passed-in lint rules to type `TestCasePrecursor` to ease further TestCase
    creation later on.
    """
    cases = []
    for rule in rules:
        if not issubclass(rule, CstLintRule):
            continue
        test_cases_for_rule = _gen_test_methods_for_rule(cast(Type[CstLintRule], rule))
        cases.append(test_cases_for_rule)
    return cases


def add_lint_rule_tests_to_module(
    module_attrs: Dict[str, Any],
    rules: LintRuleCollectionT = [],
    test_case_type: Type[unittest.TestCase] = LintRuleTestCase,
    custom_test_method_name: str = "_test_method",
) -> None:
    """
    Generates classes inheriting from `unittest.TestCase` from the data available in `rules` and adds these to module_attrs.
    The goal is to facilitate unit test discovery by Python's `unittest` framework. This will provide the capability of
    testing your lint rules by running commands such as `python -m unittest <your testing module name>`.

    module_attrs: A dictionary of attributes we want to add these test cases to. If adding to a module, you can pass `globals()` as the argument.

    rules: A collection of classes extending `CstLintRule` to be converted to test cases.

    test_case_type: A class extending Python's `unittest.TestCase` that implements a custom test method for testing lint rules to serve as a stencil for test cases.
    New classes will be generated, and named after each lint rule. They will inherit directly from the class passed into `test_case_type`.
    If argument is omitted, will default to the `LintRuleTestCase` class from fixit.common.testing.

    custom_test_method_name: A member method of the class passed into `test_case_type` parameter that contains the logic around asserting success or failure of
    CstLintRule's `ValidTestCase` and `InvalidTestCase` test cases. The method will be dynamically renamed to `test_<VALID/INVALID>_<test case index>` for discovery
    by unittest. If argument is omitted, `add_lint_rule_tests_to_module` will look for a test method named `_test_method` member of `test_case_type`.
    """
    for test_case in _gen_all_test_methods(rules):
        rule_name = test_case.rule.__name__
        test_methods_to_add: Dict[str, Callable] = dict()

        for test_method_name, test_method_data in test_case.test_methods.items():
            metadata_wrapper = None
            if isinstance(
                test_method_data,
                (InvalidTypeDependentTestCase, ValidTypeDependentTestCase),
            ):
                metadata_wrapper = test_method_data.type_inference_wrapper

            def test_method(
                self: Type[LintRuleTestCase],
                data: Union[ValidTestCase, InvalidTestCase] = test_method_data,
                rule: Type[CstLintRule] = test_case.rule,
                metadata_wrapper: Optional[MetadataWrapper] = metadata_wrapper,
            ) -> None:
                return getattr(self, custom_test_method_name)(
                    data, rule, metadata_wrapper
                )

            test_method.__name__ = test_method_name
            test_methods_to_add[test_method_name] = test_method

        test_case_class = type(rule_name, (test_case_type,), test_methods_to_add)
        module_attrs[rule_name] = test_case_class
