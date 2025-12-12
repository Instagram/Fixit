# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
import textwrap
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Collection, Dict, List, Mapping, Sequence, Type, Union

from .engine import diff_violation, LintRunner
from .ftypes import Config, Invalid, Valid
from .rule import LintRule


def _dedent(src: str) -> str:
    src = re.sub(r"\A\n", "", src)
    return textwrap.dedent(src)


def get_fixture_path(
    fixture_top_dir: Path, rule_module: str, rules_package: str
) -> Path:
    subpackage: str = rule_module.split(f"{rules_package}.", 1)[-1]
    fixture_subdir = subpackage.replace(".", "/")
    return fixture_top_dir / fixture_subdir


def validate_patch(report: Any, test_case: Invalid) -> None:
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
    rule: LintRule
    test_methods: Mapping[
        str,
        Union[Valid, Invalid],
    ]
    fixture_paths: Mapping[str, Path]


class LintRuleTestCase(unittest.TestCase):
    def _test_method(
        self,
        test_case: Union[Valid, Invalid],
        rule: LintRule,
    ) -> None:
        path = Path.cwd() / (
            "valid.py" if isinstance(test_case, Valid) else "invalid.py"
        )
        config = Config(path=path)
        source_code = _dedent(test_case.code)
        runner = LintRunner(path, source_code.encode())
        reports = list(runner.collect_violations([rule], config))

        if isinstance(test_case, Valid):
            self.assertEqual(
                len(reports),
                0,
                'Expected zero reports for this "valid" test case. Instead, found:\n'
                + "\n".join(str(e) for e in reports),
            )
            return

        self.assertGreater(
            len(reports),
            0,
            'Expected a report for this "invalid" test case but `self.report` was '
            + "not called:\n"
            + test_case.code,
        )

        for report in reports:
            if test_case.range is not None:
                self.assertEqual(test_case.range, report.range)

            if test_case.expected_message is not None:
                self.assertEqual(test_case.expected_message, report.message)

        if test_case.expected_replacement:
            # make sure we produced expected final code
            expected_code = _dedent(test_case.expected_replacement)
            modified_code = runner.apply_replacements(reports).bytes.decode()
            self.assertMultiLineEqual(expected_code, modified_code)

            if len(reports) == 1:
                # make sure we generated a reasonable diff
                expected_diff = diff_violation(path, runner.module, reports[0])
                self.assertEqual(expected_diff, report.diff)


def gen_test_methods_for_rule(rule: LintRule) -> TestCasePrecursor:
    """
    Aggregates all of the cases inside a single LintRule's VALID and INVALID
    attributes and maps them to altered names with a `test_` prefix so that 'unittest'
    can discover them later on and an index postfix so that individual tests can be
    selected from the command line.
    """
    valid_tcs = {}
    invalid_tcs = {}
    fixture_paths: Dict[str, Path] = {}
    for idx, test_case_or_str in enumerate(rule.VALID):
        name = f"test_VALID_{idx}"
        valid_test_case = (
            Valid(code=test_case_or_str)
            if isinstance(test_case_or_str, str)
            else test_case_or_str
        )
        valid_tcs[name] = valid_test_case
    for idx, inv_test_case_or_str in enumerate(rule.INVALID):
        name = f"test_INVALID_{idx}"
        invalid_test_case = (
            Invalid(code=inv_test_case_or_str)
            if isinstance(inv_test_case_or_str, str)
            else inv_test_case_or_str
        )
        invalid_tcs[name] = invalid_test_case

    return TestCasePrecursor(
        rule=rule,
        test_methods={**valid_tcs, **invalid_tcs},
        fixture_paths=fixture_paths,
    )


def gen_all_test_methods(rules: Collection[LintRule]) -> Sequence[TestCasePrecursor]:
    """
    Converts all passed-in lint rules to type `TestCasePrecursor` to ease further TestCase
    creation later on.
    """
    cases = []
    for rule in rules:
        if not isinstance(rule, LintRule):
            continue
        test_cases_for_rule = gen_test_methods_for_rule(rule)
        cases.append(test_cases_for_rule)
    return cases


def generate_lint_rule_test_cases(
    rules: Collection[LintRule],
) -> List[Type[unittest.TestCase]]:
    test_case_classes: List[Type[unittest.TestCase]] = []
    for test_case in gen_all_test_methods(rules):
        rule_name = type(test_case.rule).__name__
        test_methods_to_add: Dict[str, Callable[..., Any]] = {}

        for test_method_name, test_method_data in test_case.test_methods.items():

            def test_method(
                self: LintRuleTestCase,
                data: Union[Valid, Invalid] = test_method_data,
                rule: LintRule = test_case.rule,
            ) -> None:
                # instantiate a new rule for every test
                rule_ty = type(rule)
                return self._test_method(data, rule_ty())

            test_method.__name__ = test_method_name
            test_methods_to_add[test_method_name] = test_method

        test_case_class = type(rule_name, (LintRuleTestCase,), test_methods_to_add)
        test_case_classes.append(test_case_class)

    return test_case_classes


def add_lint_rule_tests_to_module(
    module_attrs: Dict[str, Any], rules: Collection[LintRule]
) -> None:
    """
    Generates classes inheriting from `unittest.TestCase` from the data available in `rules` and adds these to module_attrs.
    The goal is to facilitate unit test discovery by Python's `unittest` framework. This will provide the capability of
    testing your lint rules by running commands such as `python -m unittest <your testing module name>`.

    module_attrs: A dictionary of attributes we want to add these test cases to. If adding to a module, you can pass `globals()` as the argument.

    rules: A collection of classes extending `LintRule` to be converted to test cases.

    test_case_type: A class extending Python's `unittest.TestCase` that implements a custom test method for testing lint rules to serve as a stencil for test cases.
    New classes will be generated, and named after each lint rule. They will inherit directly from the class passed into `test_case_type`.
    If argument is omitted, will default to the `LintRuleTestCase` class from fixit.common.testing.

    custom_test_method_name: A member method of the class passed into `test_case_type` parameter that contains the logic around asserting success or failure of
    LintRule's `Valid` and `Invalid` test cases. The method will be dynamically renamed to `test_<VALID/INVALID>_<test case index>` for discovery
    by unittest. If argument is omitted, `add_lint_rule_tests_to_module` will look for a test method named `_test_method` member of `test_case_type`.

    fixture_dir: The directory in which fixture files for the passed rules live. Necessary only if any lint rules require fixture data for testing.

    rules_package: The name of the rules package. This will be used during the search for fixture files and provides insight into the structure of the fixture directory.
    The structure of the fixture directory is automatically assumed to mirror the structure of the rules package, eg: `<rules_package>.submodule.module.rule_class` should
    have fixture files in `<fixture_dir>/submodule/module/rule_class/`.
    """
    test_case_classes = generate_lint_rule_test_cases(rules)
    for test_case_class in test_case_classes:
        module_attrs[test_case_class.__name__] = test_case_class

    # Rewrite the module for each generated test case to match the location calling
    # this function. This enables better integration with test case discovery methods
    # that depend on listing test cases separately from running them.
    if "__package__" in module_attrs:
        test_module = module_attrs.get("__package__")
        assert isinstance(test_module, str)
        for test_case_class in test_case_classes:
            test_case_class.__module__ = test_module
