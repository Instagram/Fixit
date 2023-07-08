# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Union

import libcst as cst
import libcst.matchers as m

from fixit import Invalid, LintRule, Valid


class NoRedundantArgumentsSuperRule(LintRule):
    """
    Remove redundant arguments when using super for readability.
    """

    MESSAGE: str = (
        "Do not use arguments when calling super for the parent class. See "
        + "https://www.python.org/dev/peps/pep-3135/"
    )
    VALID = [
        Valid(
            """
            class Foo(Bar):
                def foo(self, bar):
                    super().foo(bar)
            """
        ),
        Valid(
            """
            class Foo(Bar):
                def foo(self, bar):
                    super(Bar, self).foo(bar)
            """
        ),
        Valid(
            """
            class Foo(Bar):
                @classmethod
                def foo(cls, bar):
                    super(Bar, cls).foo(bar)
            """
        ),
        Valid(
            """
            class Foo:
                class InnerBar(Bar):
                    def foo(self, bar):
                        pass

                class InnerFoo(InnerBar):
                    def foo(self, bar):
                        super(InnerBar, self).foo(bar)
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            class Foo(Bar):
                def foo(self, bar):
                    super(Foo, self).foo(bar)
            """,
            expected_replacement="""
            class Foo(Bar):
                def foo(self, bar):
                    super().foo(bar)
            """,
        ),
        Invalid(
            """
            class Foo(Bar):
                @classmethod
                def foo(cls, bar):
                    super(Foo, cls).foo(bar)
            """,
            expected_replacement="""
            class Foo(Bar):
                @classmethod
                def foo(cls, bar):
                    super().foo(bar)
            """,
        ),
        Invalid(
            """
            class Foo:
                class InnerFoo(Bar):
                    def foo(self, bar):
                        super(Foo.InnerFoo, self).foo(bar)
            """,
            expected_replacement="""
            class Foo:
                class InnerFoo(Bar):
                    def foo(self, bar):
                        super().foo(bar)
            """,
        ),
        Invalid(
            """
            class Foo:
                class InnerFoo(Bar):
                    class InnerInnerFoo(Bar):
                        def foo(self, bar):
                            super(Foo.InnerFoo.InnerInnerFoo, self).foo(bar)
            """,
            expected_replacement="""
            class Foo:
                class InnerFoo(Bar):
                    class InnerInnerFoo(Bar):
                        def foo(self, bar):
                            super().foo(bar)
            """,
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_classes: List[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.current_classes.append(node.name.value)

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self.current_classes.pop()

    def leave_Call(self, original_node: cst.Call) -> None:
        if self.current_classes and m.matches(
            original_node,
            m.Call(
                func=m.Name("super"),
                args=[
                    m.Arg(value=self._build_arg_class_matcher()),
                    m.Arg(),
                ],
            ),
        ):
            self.report(original_node, replacement=original_node.with_changes(args=()))

    def _build_arg_class_matcher(self) -> Union[m.Attribute, m.Name]:
        matcher: Union[m.Name, m.Attribute] = m.Name(value=self.current_classes[0])

        # For nested classes, we need to match attributes, so we can target
        # `super(Foo.InnerFoo, self)` for example.
        if len(self.current_classes) > 1:
            for class_name in self.current_classes[1:]:
                matcher = m.Attribute(value=matcher, attr=m.Name(value=class_name))

        return matcher
