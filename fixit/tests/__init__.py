# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fixit.common.testing import add_lint_rule_tests_to_module
from fixit.rule_lint_engine import get_rules


add_lint_rule_tests_to_module(globals(), get_rules())
