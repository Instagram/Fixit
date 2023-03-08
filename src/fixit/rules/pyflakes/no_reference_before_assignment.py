# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class NoReferenceBeforeAssignmentRule(CstLintRule):
    """
    Local variables should be defined before the are referenced.

    Autofix: N/A
    """

    CUSTOM_MESSAGE = ("Local variable {name} was referenced without "
                      "being defined in the current scope. Either define"
                      " it locally or use the `global` keyword to access"
                      " a global variable.")

    METADATA_DEPENDENCIES = (cst.metadata.ScopeProvider,)

    def __init__(self) -> None:
        super().__init__()

    def visit_Name(self, node: cst.Name) -> None:
        try:
            metadata = self.get_metadata(cst.metadata.ScopeProvider, node)
            assert metadata is not None
            accesses = metadata.accesses
        except KeyError:
            # Not all Names have ExpressionContext
            return
        for access in accesses:
            if access.node is node and len(access.referents) == 0:
                assert isinstance(access.node, cst.Name)
                name = access.node.value
                self.report(node, self.CUSTOM_MESSAGE.format(name=name))

    VALID = [
        Valid(
            """
            y = 2 + 3
            """
        ),
        Valid(
            """
            a = 2
            y = a + 3
            """
        ),
        Valid(
            """
            a = 2

            def fn():
                return a + 3
            """
        ),
        Valid(
            """
            a = abs(1.333)
            """
        ),
        Valid(
            """
            a = [2**i for i in (1, 2, 3)]
            """
        ),
    ]

    INVALID = [
        Invalid(
            """
            y = a + 3
            a = 2
            """
        ),
        Invalid(
            """
            def fn():
                return a + 3
            """
        ),
        Invalid(
            """
            a = foo(1.333)
            """
        ),
        Invalid(
            """
            a = [2**j for i in (1, 2, 3)]
            """
        ),
    ]
