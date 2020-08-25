# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class NoInheritFromObjectRule(CstLintRule):
    """
    In Python 3, a class is inherited from ``object`` by default.
    Explicitly inheriting from ``object`` is redundant, so removing it keeps the code simpler.
    """
    MESSAGE = "Inheriting from object is a no-op.  'class Foo:' is just fine =)"
    VALID = [
        Valid("class A(something):    pass"),
        Valid(
            """
            class A:
                pass"""
        ),
    ]
    INVALID = [
        Invalid(
            """
            class B(object):
                pass""",
            line=1,
            column=1,
            expected_replacement="""
                class B:
                    pass""",
        ),
        Invalid(
            """
            class B(object, A):
                pass""",
            line=1,
            column=1,
            expected_replacement="""
                class B(A):
                    pass""",
        ),
    ]

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        new_bases = tuple(
            base for base in node.bases if not m.matches(base.value, m.Name("object"))
        )

        if tuple(node.bases) != new_bases:
            # reconstruct classdef, removing parens if bases and keywords are empty
            new_classdef = node.with_changes(
                bases=new_bases,
                lpar=cst.MaybeSentinel.DEFAULT,
                rpar=cst.MaybeSentinel.DEFAULT,
            )

            # report warning and autofix
            self.report(node, replacement=new_classdef)
