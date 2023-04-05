# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fixit import CSTLintRule, InvalidTestCase, ValidTestCase
import libcst

class HollywoodNameRule(CSTLintRule):
    # clean code samples
    VALID = [
        ValidTestCase('name = "Susan"'),
    ]
    # code that triggers this rule
    INVALID = [
        InvalidTestCase('name = "Paul"'),
    ]

    def visit_SimpleString(self, node: libcst.SimpleString) -> None:
        if node.value in ('"Paul"', "'Paul'"):
            self.report(node, "It's underproved!")
