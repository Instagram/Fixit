# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class NoUndefinedNameRule(CstLintRule):
    """
    The variable name is either undefined, or it's imported implicitly
    through a `from ... import *` statement.

    Autofix: N/A
    """

    METADATA_DEPENDENCIES = (cst.metadata.ScopeProvider,)

    def __init__(self) -> None:
        super().__init__()
        self.has_import_star = False

    def message(self, name: str) -> str:
        if not self.has_import_star:
            return f"{name} must be defined before use"
        else:
            return (f"{name} is either undefined or it has been defined "
                   "implicitly through a `from ... import *` statement. "
                   f"Define {name}, changing any import-star statements "
                    "to explicit imports as necessary.")

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if isinstance(node.names, cst.ImportStar):
            self.has_import_star = True

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
                self.report(node, self.message(name))

    VALID = [
        Valid(
            """
            y = 1 + 2
            """
        ),
        Valid(
            """
            def b(l):
                return sum(l)

            x = b([1, 3, 5, 6, 8])
            """
        ),
        Valid(
            """
            from a import *
            import c

            x = c.d([1, 3, 5, 6, 8])
            """
        ),
        Valid(
            """
            from a import b

            def fn():
                return b([1, 3, 5, 6, 8])
            """
        ),
        Valid(
            """
            from a import b

            x = [1, 3, 5, 6, 8]
            y = [2, 4, 6, 7, 9]

            z = [b(l) for l in [x, y]]
            """
        ),
        Valid(
            """
            for i in [1, 3, 5, 6, 8]:
                print(i)
            """
        ),
        Valid(
            """
            def fn():
                global b
                b = 3

            x = b + 2
            """
        ),
    ]

    INVALID = [
        Invalid(
            """
            def b(l: List[int]):
                return sum(l)
            
            x = b([1, 3, 5, 6, 8])
            """
        ),
        Invalid(
            """
            x = b([1, 3, 5, 6, 8])

            def b(l):
                return sum(l)
            """
        ),
        Invalid(
            """
            from a import *

            x = b([1, 3, 5, 6, 8])
            """
        ),
        Invalid(
            """
            from a import b

            def fn():
                x = b([1, 3, 5, 6, 8])

            y = x + 2
            """
        ),
    ]
