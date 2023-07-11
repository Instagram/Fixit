# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst
from fixit import Invalid, LintRule, Valid


class HollywoodName(LintRule):
    # clean code samples
    VALID = [
        Valid('name = "Susan"'),
        Valid("print('Terry')"),
    ]
    # code that triggers this rule
    INVALID = [
        Invalid('name = "Paul"', expected_replacement='name = "Mary"'),
        Invalid("print('Paul')", expected_replacement='print("Mary")'),
    ]

    def visit_SimpleString(self, node: libcst.SimpleString) -> None:
        if node.value in ('"Paul"', "'Paul'"):
            new_node = libcst.SimpleString('"Mary"')
            self.report(node, "It's underproved!", replacement=new_node)
