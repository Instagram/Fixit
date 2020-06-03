# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
import fixit.tests.test_rule_lint_engine
import fixit.tests.test_rules


for lint_rule, test_case in test_rules.setupModule()[0].items():
    """ Add the unittest.TestCase types returned from setupModule to the module's attribute """
    setattr(test_rules, lint_rule, test_case)
