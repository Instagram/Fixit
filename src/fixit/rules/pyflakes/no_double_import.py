# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from collections import defaultdict
from typing import Dict, List, Set, Union

import libcst as cst

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class NoDoubleImportRule(CstLintRule):
    """
    Delete double imports.
    """

    METADATA_DEPENDENCIES = (cst.metadata.ScopeProvider,)

    def __init__(self) -> None:
        super().__init__()
        self.import_names: Dict[cst.metadata.Scope, Set[str]] = defaultdict(set)
        self.double_imports: Dict[Union[cst.Import, cst.ImportFrom], Set[str]] = defaultdict(set)

    def _message(self, names) -> str:
        def _name(l: List[str]):
            assert l
            if len(l) == 1:
                return l[0]
            elif len(l) == 2:
                return l[0] + " and " + l[1]
            else:
                return ", ".join(l[:-1]) + "and " + l[-1]
        name: str = _name(names)
        was: str = "was" if len(names) == 1 else "were"
        return (f"{name} {was} imported more than once")

    def _get_name_repr(self, name: cst.BaseExpression) -> str:
        if isinstance(name, cst.Name):
            return name.value
        assert isinstance(name, cst.Attribute)
        return self._get_name_repr(name.value) + "." + name.attr.value

    def get_double_import(self, node: Union[cst.Import, cst.ImportFrom]) -> None:
        if isinstance(node.names, cst.ImportStar):
            return
        metadata = self.get_metadata(cst.metadata.ScopeProvider, node)
        assert isinstance(metadata, cst.metadata.Scope)
        for import_alias in node.names:
            name = import_alias.asname.name if import_alias.asname is not None else import_alias.name
            name_repr = self._get_name_repr(name)
            if name_repr in self.import_names[metadata]:
                self.double_imports[node].add(name_repr)
            self.import_names[metadata].add(name_repr)

    def delete_double_import(
        self,
        node: Union[cst.Import, cst.ImportFrom],
    ) -> None:
        if node not in self.double_imports or isinstance(node.names, cst.ImportStar):
            return
        names_to_keep: List[cst.CSTNode] = []
        double_imports: List[str] = []
        for import_alias in node.names:
            name = import_alias.asname.name if import_alias.asname is not None else import_alias.name
            name_repr = self._get_name_repr(name)
            if name_repr in self.double_imports[node]:
                double_imports.append(name_repr)
            else:
                names_to_keep.append(import_alias.with_changes(comma=cst.MaybeSentinel.DEFAULT))
        if len(names_to_keep) == 0:
            self.report(node, message=self._message(double_imports), replacement=cst.RemovalSentinel.REMOVE)
        else:
            new_node = node.with_changes(names=names_to_keep)
            self.report(node, message=self._message(double_imports), replacement=new_node)

    def visit_Import(self, node: cst.Import) -> None:
        self.get_double_import(node)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self.get_double_import(node)

    def leave_Import(self, node: cst.Import) -> None:
        return self.delete_double_import(node)

    def leave_ImportFrom(self, node: cst.ImportFrom) -> None:
        return self.delete_double_import(node)

    VALID = [
        Valid(
            """
            import a

            x = a.b([1, 3, 5, 6, 8])
            """
        ),
        Valid(
            """
            def fn1():
                import a
                return a.b

            def fn2():
                import a
                return a.c
            """
        ),
        Valid(
            # valid, not good
            """
            import a as f
            import a
            """
        ),
        Valid(
            """
            import a
            from a import b
            """
        ),
        Valid(
            """
            import a
            import a.b.c.d
            """
        ),
        Valid(
            """
            import a
            from a import *
            """
        ),
        # This is allowable to cover the case that we have a `from a import fn`
        # statement in another file 
        Valid(
        """
            import a

            def fn():
                import a
                return a.b
        """
        )
    ]

    INVALID = [
        Invalid(
            """
            import a
            import b
            import a
            """,
            expected_replacement="""
            import a
            import b
            """,
        ),
        Invalid(
            """
            import g, e as g

            x = g.b([1, 3, 5, 6, 8])
            """,
            expected_replacement="""
            import e as g

            x = g.b([1, 3, 5, 6, 8])
            """,
        ),
        Invalid(
            """
            import a, b, a
            """,
            expected_replacement="""
            import a, b
            """,
        ),
        Invalid(
            """
            import a, b
            import a
            """,
            expected_replacement="""
            import a, b
            """,
        ),
        # TODO(@ansley): The next two cases will be autofixed as shown in the
        # "expected replacement" section, although this isn't the best way to
        # handle the situation. We should add additional logic for this special
        # case or create a completely different lint rule.
        Invalid(
            """
            import a
            from x import a
            """,
            expected_replacement="""
            import a
            """,
        ),
        Invalid(
            """
            from x import a
            from y import a
            """,
            expected_replacement="""
            from x import a
            """,
        ),
    ]
