# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Union

import libcst as cst
from libcst.metadata import (
    Assignment,
    QualifiedName,
    QualifiedNameProvider,
    QualifiedNameSource,
    ScopeProvider,
)

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


CLS = "cls"


class _RenameTransformer(cst.CSTTransformer):
    def __init__(
        self, names: List[Union[cst.Name, cst.Attribute]], new_name: str
    ) -> None:
        self.names = names
        self.new_name = new_name

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        # Yes this is linear search. We could potentially create a set out of the list,
        # but in most cases there are so few references to the renamed variable that the
        # overhead of creating a set + computing hashes on lookup would likely outweigh
        # any savings. Did not actually benchmark. This code runs extremely rarely IRL.
        if original_node in self.names:
            return original_node.with_changes(value=self.new_name)
        return updated_node


class ClsInClassmethodRule(CstLintRule):
    METADATA_DEPENDENCIES = (QualifiedNameProvider, ScopeProvider)
    MESSAGE = "when using @classmethod, the first argument must be 'cls'."
    VALID = [
        Valid(
            """
            class foo:
                # classmethod with cls first arg.
                @classmethod
                def cm(cls, a, b, c):
                    pass
            """
        ),
        Valid(
            """
            class foo:
                # non-classmethod with non-cls first arg.
                def nm(self, a, b, c):
                    pass
            """
        ),
        Valid(
            """
            class foo:
                # staticmethod with non-cls first arg.
                @staticmethod
                def sm(a):
                    pass
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            class foo:
                # No args at all.
                @classmethod
                def cm():
                    pass
            """,
            expected_replacement="""
            class foo:
                # No args at all.
                @classmethod
                def cm(cls):
                    pass
            """,
        ),
        Invalid(
            """
            class foo:
                # Single arg + reference.
                @classmethod
                def cm(a):
                    return a
            """,
            expected_replacement="""
            class foo:
                # Single arg + reference.
                @classmethod
                def cm(cls):
                    return cls
            """,
        ),
        Invalid(
            """
            class foo:
                # Another "cls" exists: do not autofix.
                @classmethod
                def cm(a):
                    cls = 2
            """,
        ),
        Invalid(
            """
            class foo:
                # Multiple args + references.
                @classmethod
                async def cm(a, b):
                    b = a
                    b = a.__name__
            """,
            expected_replacement="""
            class foo:
                # Multiple args + references.
                @classmethod
                async def cm(cls, b):
                    b = cls
                    b = cls.__name__
            """,
        ),
        Invalid(
            """
            class foo:
                # Do not replace in nested scopes.
                @classmethod
                async def cm(a, b):
                    b = a
                    b = lambda _: a.__name__
                    def g():
                        return a.__name__

                    # Same-named vars in sub-scopes should not be replaced.
                    b = [a for a in [1,2,3]]
                    def f(a):
                        return a + 1
            """,
            expected_replacement="""
            class foo:
                # Do not replace in nested scopes.
                @classmethod
                async def cm(cls, b):
                    b = cls
                    b = lambda _: cls.__name__
                    def g():
                        return cls.__name__

                    # Same-named vars in sub-scopes should not be replaced.
                    b = [a for a in [1,2,3]]
                    def f(a):
                        return a + 1
            """,
        ),
        Invalid(
            """
            # Do not replace in surrounding scopes.
            a = 1

            class foo:
                a = 2

                def im(a):
                    a = a

                @classmethod
                def cm(a):
                    a[1] = foo.cm(a=a)
            """,
            expected_replacement="""
            # Do not replace in surrounding scopes.
            a = 1

            class foo:
                a = 2

                def im(a):
                    a = a

                @classmethod
                def cm(cls):
                    cls[1] = foo.cm(a=cls)
            """,
        ),
        Invalid(
            """
            def another_decorator(x): pass

            class foo:
                # Multiple decorators.
                @another_decorator
                @classmethod
                @another_decorator
                async def cm(a, b, c):
                    pass
            """,
            expected_replacement="""
            def another_decorator(x): pass

            class foo:
                # Multiple decorators.
                @another_decorator
                @classmethod
                @another_decorator
                async def cm(cls, b, c):
                    pass
            """,
        ),
    ]

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        if not any(
            QualifiedNameProvider.has_name(
                self,
                decorator.decorator,
                QualifiedName(
                    name="builtins.classmethod", source=QualifiedNameSource.BUILTIN
                ),
            )
            for decorator in node.decorators
        ):
            return  # If it's not a @classmethod, we are not interested.
        if not node.params.params:
            # No params, but there must be the 'cls' param.
            # Note that pyre[47] already catches this, but we also generate
            # an autofix, so it still makes sense for us to report it here.
            new_params = node.params.with_changes(
                params=(cst.Param(name=cst.Name(value=CLS)),)
            )
            repl = node.with_changes(params=new_params)
            self.report(node, replacement=repl)
            return

        p0_name = node.params.params[0].name
        if p0_name.value == CLS:
            return  # All good.

        # Rename all assignments and references of the first param within the
        # function scope, as long as they are done via a Name node.
        # We rely on the parser to correctly derive all
        # assigments and references within the FunctionScope.
        # The Param node's scope is our classmethod's FunctionScope.
        scope = self.get_metadata(ScopeProvider, p0_name, None)
        if not scope:
            # Cannot autofix without scope metadata. Only report in this case.
            # Not sure how to repro+cover this in a unit test...
            # If metadata creation fails, then the whole lint fails, and if it succeeds,
            # then there is valid metadata. But many other lint rule implementations contain
            # a defensive scope None check like this one, so I assume it is necessary.
            self.report(node)
            return

        if scope[CLS]:
            # The scope already has another assignment to "cls".
            # Trying to rename the first param to "cls" as well may produce broken code.
            # We should therefore refrain from suggesting an autofix in this case.
            self.report(node)
            return

        refs: List[Union[cst.Name, cst.Attribute]] = []
        assignments = scope[p0_name.value]
        for a in assignments:
            if isinstance(a, Assignment):
                assign_node = a.node
                if isinstance(assign_node, cst.Name):
                    refs.append(assign_node)
                elif isinstance(assign_node, cst.Param):
                    refs.append(assign_node.name)
                # There are other types of possible assignment nodes: ClassDef,
                # FunctionDef, Import, etc. We deliberately do not handle those here.
            refs += [r.node for r in a.references]

        repl = node.visit(_RenameTransformer(refs, CLS))
        self.report(node, replacement=repl)
