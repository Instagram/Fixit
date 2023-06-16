# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Any, cast, Optional, Set
from unittest import TestCase

from .. import ftypes


class TypesTest(TestCase):
    def test_qualified_rule(self) -> None:
        valid: Set[ftypes.QualifiedRule] = set()

        for value, expected in (
            ("", None),
            ("foo-bar", None),
            ("foo/bar", None),
            ("foo", {"local": None, "module": "foo", "name": None}),
            ("foo.bar", {"local": None, "module": "foo.bar", "name": None}),
            ("foo.bar:Baz", {"local": None, "module": "foo.bar", "name": "Baz"}),
            (".foo", {"local": ".", "module": ".foo", "name": None}),
            (".foo.bar", {"local": ".", "module": ".foo.bar", "name": None}),
            (".foo.bar:Baz", {"local": ".", "module": ".foo.bar", "name": "Baz"}),
            ("..foo", None),
        ):
            with self.subTest(value):
                match = ftypes.QualifiedRuleRegex.match(value)
                if expected is not None:
                    if match is None:
                        self.fail(f"{value!r} should match QualifiedRule")
                    self.assertEqual(expected, match.groupdict())

                    kwargs = cast(ftypes.QualifiedRuleRegexResult, match.groupdict())
                    rule = ftypes.QualifiedRule(**kwargs)
                    self.assertEqual(expected["local"], rule.local)
                    self.assertEqual(expected["module"], rule.module)
                    self.assertEqual(expected["name"], rule.name)

                    valid.add(rule)

                else:
                    self.assertIsNone(
                        match, f"{value!r} should not match QualifiedRule"
                    )

        self.assertSetEqual(
            {
                ftypes.QualifiedRule("foo"),
                ftypes.QualifiedRule("foo.bar"),
                ftypes.QualifiedRule("foo.bar", "Baz"),
                ftypes.QualifiedRule(".foo", local="."),
                ftypes.QualifiedRule(".foo.bar", local="."),
                ftypes.QualifiedRule(".foo.bar", "Baz", local="."),
            },
            valid,
        )

    def test_tags_parser(self) -> None:
        Tags = ftypes.Tags

        for value, expected in (
            (None, Tags()),
            ("", Tags()),
            ("foo", Tags(("foo",))),
            ("foo, bar", Tags(("bar", "foo"))),
            ("foo, !bar", Tags(("foo",), ("bar",))),
            ("foo, -bar, foo, glob", Tags(("foo", "glob"), ("bar",))),
        ):
            with self.subTest(value):
                result = Tags.parse(value)
                self.assertEqual(expected, result)

    def test_tags_bool(self) -> None:
        Tags = ftypes.Tags
        tags: Optional[str]

        for tags in (
            "hello",
            "!hello",
            "hello,world",
            "hello,^world",
        ):
            self.assertTrue(Tags.parse(tags))

        for tags in (
            None,
            "",
        ):
            self.assertFalse(Tags.parse(tags))

    def test_tags_contains(self) -> None:
        Tags = ftypes.Tags

        value: Any
        for value, tags in (
            ("", ""),
            ("", "!hello"),
            ("hello", ""),
            ("hello", "hello"),
            ("hello", "!world"),
            ("hello", "hello, ^world"),
            ([], ""),
            ([], "!hello"),
            (["hello", "world"], ""),
            (["hello", "world"], "hello"),
            (["hello", "world"], "world"),
            (["hello", "world"], "hello, world, blue"),
            (["hello", "world"], "hello, world, !blue"),
        ):
            with self.subTest(f"{value!r} in {tags!r}"):
                self.assertIn(value, Tags.parse(tags))

        for value, tags in (
            (None, ""),
            (37, ""),
            (object(), ""),
            ("", "hello"),
            ("hello", "^hello"),
            ("hello", "!hello, world"),
            ("hello", "something, -world"),
            ([], "hello"),
            (["hello", "world"], "!hello"),
            (["hello", "world"], "!world"),
            (["hello", "world"], "!hello, world, blue"),
            (["hello", "world"], "hello, !world, blue"),
        ):
            with self.subTest(f"{value!r} not in {tags!r}"):
                self.assertNotIn(value, Tags.parse(tags))
