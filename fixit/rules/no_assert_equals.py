# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class NoAssertEqualsRule(CstLintRule):
    MESSAGE: str = (
        '"assertEquals" is deprecated, use "assertEqual" instead.\n'
        + "See https://docs.python.org/2/library/unittest.html#deprecated-aliases and https://bugs.python.org/issue9424."
    )
    VALID = [Valid("self.assertEqual(a, b)")]
    INVALID = [
        Invalid(
            "self.assertEquals(a, b)",
            expected_replacement="self.assertEqual(a, b)",
        )
    ]

    def visit_Call(self, node: cst.Call) -> None:
        if m.matches(
            node,
            m.Call(func=m.Attribute(value=m.Name("self"), attr=m.Name("assertEquals"))),
        ):
            new_call = node.with_deep_changes(
                old_node=cst.ensure_type(node.func, cst.Attribute).attr,
                value="assertEqual",
            )
            self.report(node, replacement=new_call)
