# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m
from libcst._nodes.whitespace import SimpleWhitespace
from libcst.metadata import QualifiedName, QualifiedNameProvider, QualifiedNameSource

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class ExplicitFrozenDataclassRule(CstLintRule):
    """
    Encourages the use of frozen dataclass objects by telling users to specify the
    kwarg.

    Without this lint rule, most users of dataclass won't know to use the kwarg, and
    may unintentionally end up with mutable objects.
    """

    ONCALL_SHORTNAME = "instagram_server_framework"
    MESSAGE: str = (
        "When using dataclasses, explicitly specify a frozen keyword argument. "
        + "Example: `@dataclass(frozen=True)` or `@dataclass(frozen=False)`. "
        + "Docs: https://docs.python.org/3/library/dataclasses.html"
    )
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)
    VALID = [
        Valid(
            """
            @some_other_decorator
            class Cls: pass
            """
        ),
        Valid(
            """
            from dataclasses import dataclass
            @dataclass(frozen=False)
            class Cls: pass
            """
        ),
        Valid(
            """
            import dataclasses
            @dataclasses.dataclass(frozen=False)
            class Cls: pass
            """
        ),
        Valid(
            """
            import dataclasses as dc
            @dc.dataclass(frozen=False)
            class Cls: pass
            """
        ),
        Valid(
            """
            from dataclasses import dataclass as dc
            @dc(frozen=False)
            class Cls: pass
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            from dataclasses import dataclass
            @some_unrelated_decorator
            @dataclass  # not called as a function
            @another_unrelated_decorator
            class Cls: pass
            """,
            line=3,
            expected_replacement="""
            from dataclasses import dataclass
            @some_unrelated_decorator
            @dataclass(frozen=True)  # not called as a function
            @another_unrelated_decorator
            class Cls: pass
            """,
        ),
        Invalid(
            """
            from dataclasses import dataclass
            @dataclass()  # called as a function, no kwargs
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            from dataclasses import dataclass
            @dataclass(frozen=True)  # called as a function, no kwargs
            class Cls: pass
            """,
        ),
        Invalid(
            """
            from dataclasses import dataclass
            @dataclass(other_kwarg=False)
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            from dataclasses import dataclass
            @dataclass(other_kwarg=False, frozen=True)
            class Cls: pass
            """,
        ),
        Invalid(
            """
            import dataclasses
            @dataclasses.dataclass
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Cls: pass
            """,
        ),
        Invalid(
            """
            import dataclasses
            @dataclasses.dataclass()
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Cls: pass
            """,
        ),
        Invalid(
            """
            import dataclasses
            @dataclasses.dataclass(other_kwarg=False)
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            import dataclasses
            @dataclasses.dataclass(other_kwarg=False, frozen=True)
            class Cls: pass
            """,
        ),
        Invalid(
            """
            from dataclasses import dataclass as dc
            @dc
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            from dataclasses import dataclass as dc
            @dc(frozen=True)
            class Cls: pass
            """,
        ),
        Invalid(
            """
            from dataclasses import dataclass as dc
            @dc()
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            from dataclasses import dataclass as dc
            @dc(frozen=True)
            class Cls: pass
            """,
        ),
        Invalid(
            """
            from dataclasses import dataclass as dc
            @dc(other_kwarg=False)
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            from dataclasses import dataclass as dc
            @dc(other_kwarg=False, frozen=True)
            class Cls: pass
            """,
        ),
        Invalid(
            """
            import dataclasses as dc
            @dc.dataclass
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            import dataclasses as dc
            @dc.dataclass(frozen=True)
            class Cls: pass
            """,
        ),
        Invalid(
            """
            import dataclasses as dc
            @dc.dataclass()
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            import dataclasses as dc
            @dc.dataclass(frozen=True)
            class Cls: pass
            """,
        ),
        Invalid(
            """
            import dataclasses as dc
            @dc.dataclass(other_kwarg=False)
            class Cls: pass
            """,
            line=2,
            expected_replacement="""
            import dataclasses as dc
            @dc.dataclass(other_kwarg=False, frozen=True)
            class Cls: pass
            """,
        ),
    ]

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        for d in node.decorators:
            decorator = d.decorator
            if QualifiedNameProvider.has_name(
                self,
                decorator,
                QualifiedName(
                    name="dataclasses.dataclass", source=QualifiedNameSource.IMPORT
                ),
            ):
                if isinstance(decorator, cst.Call):
                    func = decorator.func
                    args = decorator.args
                else:  # decorator is either cst.Name or cst.Attribute
                    args = ()
                    func = decorator

                # pyre-fixme[29]: `typing.Union[typing.Callable(tuple.__iter__)[[], typing.Iterator[Variable[_T_co](covariant)]], typing.Callable(typing.Sequence.__iter__)[[], typing.Iterator[cst._nodes.expression.Arg]]]` is not a function.
                if not any(m.matches(arg.keyword, m.Name("frozen")) for arg in args):
                    new_decorator = cst.Call(
                        func=func,
                        args=list(args)
                        + [
                            cst.Arg(
                                keyword=cst.Name("frozen"),
                                value=cst.Name("True"),
                                equal=cst.AssignEqual(
                                    whitespace_before=SimpleWhitespace(value=""),
                                    whitespace_after=SimpleWhitespace(value=""),
                                ),
                            )
                        ],
                    )
                    self.report(d, replacement=d.with_changes(decorator=new_decorator))
