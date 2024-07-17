# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from textwrap import dedent
from unittest import TestCase

import libcst.matchers as m
from libcst import MetadataWrapper, parse_module

from ..comments import node_comments


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
