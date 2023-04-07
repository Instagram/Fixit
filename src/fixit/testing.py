# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
import textwrap
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    Union,
)

from moreorless import unified_diff

from .engine import LintRunner
from .ftypes import Config
from .rule import InvalidTestCase, LintRule, ValidTestCase


def _dedent(src: str) -> str:
    src = re.sub(r"\A\n", "", src)
    return textwrap.dedent(src)


def get_fixture_path(
    fixture_top_dir: Path, rule_module: str, rules_package: str
) -> Path:
    subpackage: str = rule_module.split(f"{rules_package}.", 1)[-1]
    fixture_subdir = subpackage.replace(".", "/")
    return fixture_top_dir / fixture_subdir


def validate_patch(report: Any, test_case: InvalidTestCase) -> None:
    patch = report.patch
    expected_replacement = test_case.expected_replacement  # type: ignore

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
        Union[ValidTestCase, InvalidTestCase],
    ]
    fixture_paths: Mapping[str, Path]


class LintRuleTestCase(unittest.TestCase):
    def _test_method(
        self,
        test_case: Union[ValidTestCase, InvalidTestCase],
        rule: LintRule,
    ) -> None:
        config = Config()
        path = Path(
            "valid.py" if isinstance(test_case, ValidTestCase) else "invalid.py"
        )
        source_code = _dedent(test_case.code)
        runner = LintRunner(path, source_code.encode())
        reports = list(runner.collect_violations([rule], config))

        if isinstance(test_case, ValidTestCase):
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
        self.assertLessEqual(
            len(reports),
            1,
            'Expected one report from this "invalid" test case. Found multiple:\n'
            + "\n".join(str(e) for e in reports),
        )

        report = reports[0]

        if test_case.range is not None:
            self.assertEqual(test_case.range, report.range)

        if test_case.expected_message is not None:
            self.assertEqual(test_case.expected_message, report.message)

        if test_case.expected_replacement:
            # make sure we produced expected final code
            expected_code = _dedent(test_case.expected_replacement)
            modified_code = runner.apply_replacements([report]).decode()
            self.assertMultiLineEqual(expected_code, modified_code)

            # make sure we generated a reasonable diff
            expected_diff = unified_diff(
                source_code, expected_code, filename=path.name, n=1
            )
            self.assertEqual(expected_diff, report.diff)


def _gen_test_methods_for_rule(
    rule: LintRule, fixture_dir: Path, rules_package: str
) -> TestCasePrecursor:
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
            ValidTestCase(code=test_case_or_str)
            if isinstance(test_case_or_str, str)
            else test_case_or_str
        )
        valid_tcs[name] = valid_test_case
    for idx, inv_test_case_or_str in enumerate(rule.INVALID):
        name = f"test_INVALID_{idx}"
        invalid_test_case = (
            InvalidTestCase(code=inv_test_case_or_str)
            if isinstance(inv_test_case_or_str, str)
            else inv_test_case_or_str
        )
        invalid_tcs[name] = invalid_test_case

    return TestCasePrecursor(
        rule=rule,
        test_methods={**valid_tcs, **invalid_tcs},
        fixture_paths=fixture_paths,
    )


def _gen_all_test_methods(
    rules: Collection[LintRule], fixture_dir: Path, rules_package: str
) -> Sequence[TestCasePrecursor]:
    """
    Converts all passed-in lint rules to type `TestCasePrecursor` to ease further TestCase
    creation later on.
    """
    cases = []
    for rule in rules:
        if not isinstance(rule, LintRule):
            continue
        test_cases_for_rule = _gen_test_methods_for_rule(
            rule, fixture_dir, rules_package
        )
        cases.append(test_cases_for_rule)
    return cases


def add_lint_rule_tests_to_module(
    module_attrs: Dict[str, Any],
    rules: Collection[LintRule],
    test_case_type: Type[unittest.TestCase] = LintRuleTestCase,
    custom_test_method_name: str = "_test_method",
    fixture_dir: Optional[Path] = None,
    rules_package: str = "",
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
    LintRule's `ValidTestCase` and `InvalidTestCase` test cases. The method will be dynamically renamed to `test_<VALID/INVALID>_<test case index>` for discovery
    by unittest. If argument is omitted, `add_lint_rule_tests_to_module` will look for a test method named `_test_method` member of `test_case_type`.

    fixture_dir: The directory in which fixture files for the passed rules live. Necessary only if any lint rules require fixture data for testing.

    rules_package: The name of the rules package. This will be used during the search for fixture files and provides insight into the structure of the fixture directory.
    The structure of the fixture directory is automatically assumed to mirror the structure of the rules package, eg: `<rules_package>.submodule.module.rule_class` should
    have fixture files in `<fixture_dir>/submodule/module/rule_class/`.
    """
    if fixture_dir is not None or rules_package:
        raise NotImplementedError("fixtures are not implemented in tests yet")
    if fixture_dir is None:
        fixture_dir = Path("")
    test_case_classes: List[Type[unittest.TestCase]] = []
    for test_case in _gen_all_test_methods(rules, fixture_dir, rules_package):
        rule_name = type(test_case.rule).__name__
        test_methods_to_add: Dict[str, Callable] = {}

        for test_method_name, test_method_data in test_case.test_methods.items():
            fixture_file = test_case.fixture_paths.get(test_method_name)

            def test_method(
                self: Type[unittest.TestCase],
                data: Union[ValidTestCase, InvalidTestCase] = test_method_data,
                rule: LintRule = test_case.rule,
                fixture_file: Optional[Path] = fixture_file,
            ) -> None:
                # instantiate a new rule for every test
                rule_ty = type(rule)
                return getattr(self, custom_test_method_name)(data, rule_ty())

            test_method.__name__ = test_method_name
            test_methods_to_add[test_method_name] = test_method

        test_case_class = type(rule_name, (test_case_type,), test_methods_to_add)
        test_case_classes.append(test_case_class)
        module_attrs[rule_name] = test_case_class

    # Rewrite the module for each generated test case to match the location calling
    # this function. This enables better integration with test case discovery methods
    # that depend on listing test cases separately from running them.
    if "__package__" in module_attrs:
        test_module = module_attrs.get("__package__")
        assert isinstance(test_module, str)
        for test_case_class in test_case_classes:
            test_case_class.__module__ = test_module
