# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import cast, Set
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
