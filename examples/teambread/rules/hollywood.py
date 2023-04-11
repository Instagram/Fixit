# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fixit import LintRule, InvalidTestCase, ValidTestCase
import libcst

class HollywoodNameRule(LintRule):
    # clean code samples
    VALID = [
        ValidTestCase('name = "Susan"'),
        ValidTestCase("print('Terry')"),
    ]
    # code that triggers this rule
    INVALID = [
        InvalidTestCase('name = "Paul"', expected_replacement='name = "Mary"'),
        InvalidTestCase("print('Paul')", expected_replacement='print("Mary")'),
    ]

    def visit_SimpleString(self, node: libcst.SimpleString) -> None:
        if node.value in ('"Paul"', "'Paul'"):
            new_node = libcst.SimpleString('"Mary"')
            self.report(node, "It's underproved!", replacement=new_node)
