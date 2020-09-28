# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Sequence

import libcst as cst
import libcst.matchers as m

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class NoAssertTrueForComparisonsRule(CstLintRule):
    """
    Finds incorrect use of ``assertTrue`` when the intention is to compare two values.
    These calls are replaced with ``assertEqual``.
    Comparisons with True, False and None are replaced with one-argument
    calls to ``assertTrue``, ``assertFalse`` and ``assertIsNone``.
    """

    MESSAGE: str = (
        '"assertTrue" does not compare its arguments, use "assertEqual" or other '
        + "appropriate functions."
    )

    VALID = [
        Valid("self.assertTrue(a == b)"),
        Valid('self.assertTrue(data.is_valid(), "is_valid() method")'),
        Valid("self.assertTrue(validate(len(obj.getName(type=SHORT))))"),
        Valid("self.assertTrue(condition, message_string)"),
    ]

    INVALID = [
        Invalid("self.assertTrue(a, 3)", expected_replacement="self.assertEqual(a, 3)"),
        Invalid(
            "self.assertTrue(hash(s[:4]), 0x1234)",
            expected_replacement="self.assertEqual(hash(s[:4]), 0x1234)",
        ),
        Invalid(
            "self.assertTrue(list, [1, 3])",
            expected_replacement="self.assertEqual(list, [1, 3])",
        ),
        Invalid(
            "self.assertTrue(optional, None)",
            expected_replacement="self.assertIsNone(optional)",
        ),
        Invalid(
            "self.assertTrue(b == a, True)",
            expected_replacement="self.assertTrue(b == a)",
        ),
        Invalid(
            "self.assertTrue(b == a, False)",
            expected_replacement="self.assertFalse(b == a)",
        ),
    ]

    def visit_Call(self, node: cst.Call) -> None:
        result = m.extract(
            node,
            m.Call(
                func=m.Attribute(value=m.Name("self"), attr=m.Name("assertTrue")),
                args=[
                    m.DoNotCare(),
                    m.Arg(
                        value=m.SaveMatchedNode(
                            m.OneOf(
                                m.Integer(),
                                m.Float(),
                                m.Imaginary(),
                                m.Tuple(),
                                m.List(),
                                m.Set(),
                                m.Dict(),
                                m.Name("None"),
                                m.Name("True"),
                                m.Name("False"),
                            ),
                            "second",
                        )
                    ),
                ],
            ),
        )

        if result:
            second_arg = result["second"]
            if isinstance(second_arg, Sequence):
                second_arg = second_arg[0]

            if m.matches(second_arg, m.Name("True")):
                new_call = node.with_changes(
                    args=[node.args[0].with_changes(comma=cst.MaybeSentinel.DEFAULT)],
                )
            elif m.matches(second_arg, m.Name("None")):
                new_call = node.with_changes(
                    func=node.func.with_deep_changes(
                        old_node=cst.ensure_type(node.func, cst.Attribute).attr,
                        value="assertIsNone",
                    ),
                    args=[node.args[0].with_changes(comma=cst.MaybeSentinel.DEFAULT)],
                )
            elif m.matches(second_arg, m.Name("False")):
                new_call = node.with_changes(
                    func=node.func.with_deep_changes(
                        old_node=cst.ensure_type(node.func, cst.Attribute).attr,
                        value="assertFalse",
                    ),
                    args=[node.args[0].with_changes(comma=cst.MaybeSentinel.DEFAULT)],
                )
            else:
                new_call = node.with_deep_changes(
                    old_node=cst.ensure_type(node.func, cst.Attribute).attr,
                    value="assertEqual",
                )

            self.report(node, replacement=new_call)
