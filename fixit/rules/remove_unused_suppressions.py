# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst

from fixit.common.base import CstLintRule


class RemoveUnusedSuppressionsRule(CstLintRule):
    MESSAGE: str = (
        "Unused lint suppression {lint_code}: This comment is not suppressing lint errors and should be removed."
    )

    def should_skip_file(self) -> bool:
        return self.context.in_tests

    def visit_Await(self, node: cst.Await) -> None:
        parent = self.context.node_stack[-2]

        if isinstance(parent, (cst.Expr, cst.Assign)) and parent.value is node:
            grand_parent = self.context.node_stack[-5]
            # for and while code block contain IndentBlock and SimpleStatementLine
            if isinstance(grand_parent, (cst.For, cst.While)):
                self.report(node)

        if (
            isinstance(parent, (cst.ListComp, cst.SetComp, cst.GeneratorExp))
            and parent.elt is node
        ):
            self.report(node)
