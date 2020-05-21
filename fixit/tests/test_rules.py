# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import TYPE_CHECKING, Mapping, Type, Union

from libcst.testing.utils import data_provider
from mypy_extensions import TypedDict

from fixit.common.base import CstLintRule
from fixit.common.testing import LintRuleTest
from fixit.rule_lint_engine import get_rules


if TYPE_CHECKING:
    from fixit.common.utils import ValidTestCase, InvalidTestCase  # noqa: F401


class TestCase(TypedDict):
    test_case: Union["ValidTestCase", "InvalidTestCase"]
    rule: Type[CstLintRule]


def _gen_test_cases() -> Mapping[str, TestCase]:
    cases = {}
    for rule in get_rules():
        if not issubclass(rule, CstLintRule):
            continue
        if hasattr(rule, "VALID"):
            # pyre-ignore[16]: `CstLintRule` has no attribute `VALID`.
            for idx, test_case in enumerate(rule.VALID):
                cases[f"{rule.__name__}_VALID_{idx}"] = {
                    "test_case": test_case,
                    "rule": rule,
                }
        if hasattr(rule, "INVALID"):
            # pyre-ignore[16]: `CstLintRule` has no attribute `INVALID`.
            for idx, test_case in enumerate(rule.INVALID):
                cases[f"{rule.__name__}_INVALID_{idx}"] = {
                    "test_case": test_case,
                    "rule": rule,
                }
    return cases


class Test(LintRuleTest):
    ONCALL_SHORTNAME = "instagram_server_framework"

    @data_provider(_gen_test_cases(), test_limit=10000)
    def test(
        self,
        test_case: Union["ValidTestCase", "InvalidTestCase"],
        rule: Type[CstLintRule],
    ) -> None:
        self._test_rule(test_case, rule=rule)

    # pyre-ignore[14]: `test_rule` overrides method defined in `LintRuleTest`
    #  inconsistently.
    def test_rule(self) -> None:
        # explicit empty test case to overwrite parent's implementation
        pass
