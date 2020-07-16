# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fixit.common.config import LintConfig, get_lint_config
from fixit.common.testing import add_lint_rule_tests_to_module
from fixit.rule_lint_engine import get_rules_from_config


# Add all the CstLintRules from `fixit.rules` package to this module as unit tests.
CONFIG: LintConfig = get_lint_config()
add_lint_rule_tests_to_module(
    globals(),
    get_rules_from_config(CONFIG),
    fixture_dir=CONFIG.fixture_dir,
    rules_package="fixit.rules",
)
