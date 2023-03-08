# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Set, Union

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

    def get_import_name(self, node: Union[cst.Import, cst.ImportFrom]) -> None:
        if isinstance(node.names, cst.ImportStar):
            return
        for import_alias in node.names:
            name = import_alias.asname.name if import_alias.asname is not None else import_alias.name
            assert isinstance(name, cst.Name)
            self.import_names.add(name.value)

    def visit_Import(self, node: cst.Import) -> None:
        self.get_import_name(node)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self.get_import_name(node)

    def visit_For(self, node: cst.For) -> None:
        assert isinstance(node.target, cst.Name)
        target = node.target.value
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
    ]

    INVALID = [
        Invalid(
            """
            import i

            for i in [1, 2, 3]:
                print(i)
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
    ]
