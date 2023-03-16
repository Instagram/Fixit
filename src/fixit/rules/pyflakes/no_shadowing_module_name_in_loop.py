# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Set

import libcst as cst

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class NoShadowingModuleNameInLoopRule(CstLintRule):
    """
    A loop variable name should not shadow an imported module's name.

    Autofix: N/A
    """

    MESSAGE = "A loop variable name should not shadow an imported module's name."

    def __init__(self) -> None:
        super().__init__()
        self.import_names: Set[str] = set()

    def visit_Import(self, node: cst.Import) -> None:
        def get_toplevel_module_name(name: cst.BaseExpression) -> str:
            if isinstance(name, cst.Name):
                return name.value
            assert isinstance(name, cst.Attribute)
            return get_toplevel_module_name(name.value)

        for import_alias in node.names:
            name = (
                import_alias.asname.name
                if import_alias.asname is not None
                else import_alias.name
            )
            self.import_names.add(get_toplevel_module_name(name))

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if isinstance(node.names, cst.ImportStar):
            return
        for import_alias in node.names:
            name = (
                import_alias.asname.name
                if import_alias.asname is not None
                else import_alias.name
            )
            assert isinstance(name, cst.Name)
            self.import_names.add(name.value)

    def visit_For(self, node: cst.For) -> None:
        targets = []
        if isinstance(node.target, cst.Name):
            targets.append(node.target.value)
        else:
            assert isinstance(node.target, cst.Tuple)
            for element in node.target.elements:
                assert isinstance(element.value, cst.Name)
                targets.append(element.value.value)
        for target in targets:
            if target in self.import_names:
                self.report(node)

    VALID = [
        Valid(
            """
            import a

            for i in [1, 2, 3]:
                print(i)
            """
        ),
        Valid(
            """
            for i in [1, 2, 3]:
                print(i)

            import i
            """
        ),
        Valid(
            """
            import i as a

            for i in [1, 2, 3]:
                print(i)
            """
        ),
        Valid(
            """
            from i import a

            for i in [1, 2, 3]:
                print(i)
            """
        ),
        Valid(
            """
            from a import i as b

            for i in [1, 2, 3]:
                print(i)
            """
        ),
        Valid(
            """
            import a.b.c

            for b in [1, 2, 3]:
                print(b)
            """
        ),
        Valid(
            """
            import a.b.c

            for c in [1, 2, 3]:
                print(c)
            """
        ),
        Valid(
            """
            from a.b import c

            for a in [1, 2, 3]:
                print(a)
            """
        ),
        Valid(
            """
            from a.b import c

            for b in [1, 2, 3]:
                print(b)
            """
        ),
        Valid(
            """
            from a import (b, c)

            for i in [1, 2, 3]:
                print(i)
            """
        ),
    ]

    INVALID = [
        Invalid(
            """
            import i.a.b

            for i in [1, 2, 3]:
                print(i)
            """
        ),
        Invalid(
            """
            import a.b

            for a in [1, 2, 3]:
                print(a)
            """
        ),
        Invalid(
            """
            from a import i

            for i in [1, 2, 3]:
                print(i)
            """
        ),
        Invalid(
            """
            import a as i

            for i in [1, 2, 3]:
                print(i)
            """
        ),
        Invalid(
            """
            from a import b as i

            for i in [1, 2, 3]:
                print(i)
            """
        ),
        Invalid(
            """
            import a

            for a, b in [zip((1, 2, 3),("foo", "bar", "baz"))]:
                print(str(a) + ". " + b)
            """
        ),
    ]
