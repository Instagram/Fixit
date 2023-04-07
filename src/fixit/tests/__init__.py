# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fixit.config import collect_rules
from fixit.ftypes import QualifiedRule

from fixit.testing import add_lint_rule_tests_to_module
from .config import ConfigTest
from .ftypes import TypesTest
from .rule import RuleTest, RunnerTest
from .smoke import SmokeTest

add_lint_rule_tests_to_module(
    globals(),
    collect_rules(enables=[QualifiedRule("fixit.rules")], disables=[]),
)
