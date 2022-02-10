# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path

from fixit import add_lint_rule_tests_to_module
from fixit.common.base import LintConfig
from fixit.common.config import get_lint_config, get_rules_for_path


# Add all the CstLintRules from `fixit.rules` package to this module as unit tests.
CONFIG: LintConfig = get_lint_config()
add_lint_rule_tests_to_module(
    globals(),
    get_rules_for_path(None),
    fixture_dir=Path(CONFIG.fixture_dir),
    rules_package="fixit.rules",
)
