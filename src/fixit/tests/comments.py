# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from textwrap import dedent
from typing import Sequence, Tuple
from unittest import TestCase

import libcst.matchers as m
from libcst import MetadataWrapper, parse_module

from ..comments import add_suppression_comment, node_comments, node_nearest_comment
from ..ftypes import LintIgnoreStyle


class CommentsTest(TestCase):
    def test_node_comments(self) -> None:
        for idx, (code, test_cases) in enumerate(
            (
                (
                    """
                    # module-level comment
                    print("hello")  # trailing comment
                    """,
                    (
                        (m.Call(func=m.Name("something")), ()),
                        (m.Call(), ["# module-level comment", "# trailing comment"]),
                    ),
                ),
                (
                    """
                    import sys

                    # leading comment
                    print("hello")  # trailing comment
                    """,
                    ((m.Call(), ["# leading comment", "# trailing comment"]),),
                ),
                (
                    """
                    import sys

                    # leading comment
                    @alpha  # first decorator comment
                    # between-decorator comment
                    @beta  # second decorator comment
                    # after-decorator comment
                    class Foo:  # trailing comment
                        pass
                    """,
                    (
                        (
                            m.ClassDef(),
                            [
                                "# leading comment",
                                "# after-decorator comment",
                                "# trailing comment",
                            ],
                        ),
                        (
                            m.Decorator(decorator=m.Name("alpha")),
                            ["# leading comment", "# first decorator comment"],
                        ),
                    ),
                ),
            ),
            start=1,
        ):
            code = dedent(code)
            module = parse_module(code)
            wrapper = MetadataWrapper(module, unsafe_skip_copy=True)
            for idx2, (matcher, expected) in enumerate(test_cases):
                with self.subTest(f"node comments {idx}-{chr(ord('a')+idx2)}"):
                    for node in m.findall(module, matcher):
                        comments = [c.value for c in node_comments(node, wrapper)]
                        self.assertEqual(sorted(expected), sorted(comments))
                        break
                    else:
                        assert expected == (), f"no node matched by {matcher}"

    def test_node_nearest_comment(self) -> None:
        test_cases: Sequence[Tuple[str, m.BaseMatcherNode, m.BaseMatcherNode]] = (
            (
                """
                    print("hello")
                    """,
                m.Call(func=m.Name("print")),
                m.TrailingWhitespace(),
            ),
            (
                """
                    print("hello")  # here
                    """,
                m.Call(func=m.Name("print")),
                m.Comment("# here"),
            ),
            (
                """
                    import sys

                    # here
                    def foo():
                        pass
                    """,
                m.FunctionDef(name=m.Name("foo")),
                m.FunctionDef(name=m.Name("foo")),
            ),
            (
                """
                    def foo():
                        pass  # here
                    """,
                m.Pass(),
                m.Comment("# here"),
            ),
            (
                """
                    items = [
                        foo,  # here
                        bar,
                    ]
                    """,
                m.Element(value=m.Name("foo")),
                m.TrailingWhitespace(comment=m.Comment("# here")),
            ),
            (
                """
                    items = [
                        foo,
                        bar,  # here
                    ]
                    """,
                m.Element(value=m.Name("bar")),
                m.TrailingWhitespace(comment=m.Comment("# here")),
            ),
            (
                """
                    import sys
                    # here
                    items = [
                        foo,
                        bar,
                    ]
                    """,
                m.List(),
                m.SimpleStatementLine(
                    leading_lines=[m.EmptyLine(comment=m.Comment("# here"))]
                ),
            ),
        )
        for idx, (code, target, expected) in enumerate(test_cases, start=1):
            with self.subTest(f"nearest node {idx}"):
                code = dedent(code)
                module = parse_module(code)
                wrapper = MetadataWrapper(module, unsafe_skip_copy=True)

                for target_node in m.findall(module, target):  # noqa: B007
                    break
                else:
                    self.fail(f"no target node matched by {target}")

                comment = node_nearest_comment(target_node, wrapper)
                self.assertTrue(
                    m.matches(comment, expected),
                    f"nearest comment did not match expected node\n----{code}----\ntarget: {target_node}\n----\nfound: {comment}",
                )

    def test_add_suppression_comment(self) -> None:
        test_cases: Sequence[
            Tuple[str, m.BaseMatcherNode, str, LintIgnoreStyle, str]
        ] = (
            (
                """
                    print("hello")
                    """,
                m.Call(func=m.Name("print")),
                "NoPrint",
                LintIgnoreStyle.fixme,
                """
                    print("hello")  # lint-fixme: NoPrint
                    """,
            ),
            (
                """
                    print("hello")  # noqa
                    """,
                m.Call(func=m.Name("print")),
                "NoPrint",
                LintIgnoreStyle.ignore,
                """
                    print("hello")  # noqa  # lint-ignore: NoPrint
                    """,
            ),
            (
                """
                    print("hello")  # noqa  # lint-fixme: SomethingElse [whatever]
                    """,
                m.Call(func=m.Name("print")),
                "NoPrint",
                LintIgnoreStyle.fixme,
                """
                    print("hello")  # noqa  # lint-fixme: NoPrint, SomethingElse [whatever]
                    """,
            ),
            (
                """
                    items = [
                        foo,
                        bar,
                    ]
                    """,
                m.Element(value=m.Name("foo")),
                "NoFoo",
                LintIgnoreStyle.fixme,
                """
                    items = [
                        foo,  # lint-fixme: NoFoo
                        bar,
                    ]
                    """,
            ),
            (
                """
                    items = [
                        foo,
                        bar,
                    ]
                    """,
                m.Element(value=m.Name("bar")),
                "NoFoo",
                LintIgnoreStyle.fixme,
                """
                    items = [
                        foo,
                        bar,  # lint-fixme: NoFoo
                    ]
                    """,
            ),
            (
                """
                    items = [
                        foo,
                        bar,
                    ]
                    """,
                m.List(),
                "SomethingWrong",
                LintIgnoreStyle.fixme,
                """
                    # lint-fixme: SomethingWrong
                    items = [
                        foo,
                        bar,
                    ]
                    """,
            ),
        )
        for idx, (code, matcher, name, style, expected) in enumerate(
            test_cases, start=1
        ):
            with self.subTest(f"add suppression {idx}"):
                expected = dedent(expected)
                code = dedent(code)
                module = parse_module(code)
                wrapper = MetadataWrapper(module, unsafe_skip_copy=True)

                for node in m.findall(module, matcher):  # noqa: B007
                    break
                else:
                    self.fail(f"no node matched by {matcher}")

                new_module = add_suppression_comment(module, node, wrapper, name, style)
                result = new_module.code
                self.assertEqual(expected, result)
