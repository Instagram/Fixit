# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import TestCase

from .. import config
from ..ftypes import Config, QualifiedRule, RawConfig, Tags, Version


class ConfigTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.td = TemporaryDirectory()
        self.tdp = Path(self.td.name).resolve()

        self.outer = self.tdp / "outer"
        self.inner = self.tdp / "outer" / "inner"
        self.inner.mkdir(parents=True)

        (self.tdp / "pyproject.toml").write_text(
            dedent(
                """
                [tool.fixit]
                root = true
                enable-root-import = true
                enable = ["more.rules"]
                disable = ["fixit.rules.SomethingSpecific"]
                python-version = "3.8"

                [[tool.fixit.overrides]]
                path = "other"
                enable = ["other.stuff", ".globalrules"]
                disable = ["fixit.rules"]
                options = {"other.stuff.Whatever"={key="value"}}
                python-version = "3.10"
                """
            )
        )
        (self.outer / ".fixit.toml").write_text(
            dedent(
                """
                [tool.fixit]
                enable = [".localrules"]
                disable = ["fixit.rules"]
                """
            )
        )
        (self.inner / "pyproject.toml").write_text(
            dedent(
                """
                [tool.fuzzball]
                something = "whatever"
                """
            )
        )
        (self.inner / "fixit.toml").write_text(
            dedent(
                """
                [tool.fixit]
                root = true
                enable = ["fake8", "make8"]
                disable = ["foo.bar"]
                unknown = "hello"
                """
            )
        )

    def tearDown(self):
        self.td.cleanup()

    def test_locate_configs(self):
        for name, path, root, expected in (
            ("top", self.tdp, None, [self.tdp / "pyproject.toml"]),
            ("top file", self.tdp / "hello.py", None, [self.tdp / "pyproject.toml"]),
            (
                "outer",
                self.outer,
                None,
                [self.outer / ".fixit.toml", self.tdp / "pyproject.toml"],
            ),
            (
                "outer file",
                self.outer / "frob.py",
                None,
                [self.outer / ".fixit.toml", self.tdp / "pyproject.toml"],
            ),
            (
                "inner",
                self.inner,
                None,
                [
                    self.inner / "fixit.toml",
                    self.inner / "pyproject.toml",
                    self.outer / ".fixit.toml",
                    self.tdp / "pyproject.toml",
                ],
            ),
            (
                "inner file",
                self.inner / "test.py",
                None,
                [
                    self.inner / "fixit.toml",
                    self.inner / "pyproject.toml",
                    self.outer / ".fixit.toml",
                    self.tdp / "pyproject.toml",
                ],
            ),
            ("outer from outer", self.outer, self.outer, [self.outer / ".fixit.toml"]),
            (
                "inner from outer",
                self.inner,
                self.outer,
                [
                    self.inner / "fixit.toml",
                    self.inner / "pyproject.toml",
                    self.outer / ".fixit.toml",
                ],
            ),
            (
                "inner from inner",
                self.inner,
                self.inner,
                [self.inner / "fixit.toml", self.inner / "pyproject.toml"],
            ),
        ):
            with self.subTest(name):
                actual = config.locate_configs(path, root)
                self.assertListEqual(expected, actual)

    def test_read_configs(self):
        # in-out priority order
        innerA = self.inner / "fixit.toml"
        innerB = self.inner / "pyproject.toml"
        outer = self.outer / ".fixit.toml"
        top = self.tdp / "pyproject.toml"

        for name, paths, expected in (
            (
                "inner",
                [innerA, innerB, outer, top],
                [
                    RawConfig(
                        innerA,
                        {
                            "root": True,
                            "enable": ["fake8", "make8"],
                            "disable": ["foo.bar"],
                            "unknown": "hello",
                        },
                    )
                ],
            ),
            (
                "inner partial",
                [innerB, outer, top],
                [
                    RawConfig(
                        outer, {"enable": [".localrules"], "disable": ["fixit.rules"]}
                    ),
                    RawConfig(
                        top,
                        {
                            "root": True,
                            "enable-root-import": True,
                            "enable": ["more.rules"],
                            "disable": ["fixit.rules.SomethingSpecific"],
                            "python-version": "3.8",
                            "overrides": [
                                {
                                    "path": "other",
                                    "enable": ["other.stuff", ".globalrules"],
                                    "disable": ["fixit.rules"],
                                    "options": {
                                        "other.stuff.Whatever": {"key": "value"}
                                    },
                                    "python-version": "3.10",
                                },
                            ],
                        },
                    ),
                ],
            ),
            (
                "outer",
                [outer, top],
                [
                    RawConfig(
                        outer, {"enable": [".localrules"], "disable": ["fixit.rules"]}
                    ),
                    RawConfig(
                        top,
                        {
                            "root": True,
                            "enable-root-import": True,
                            "enable": ["more.rules"],
                            "disable": ["fixit.rules.SomethingSpecific"],
                            "python-version": "3.8",
                            "overrides": [
                                {
                                    "path": "other",
                                    "enable": ["other.stuff", ".globalrules"],
                                    "disable": ["fixit.rules"],
                                    "options": {
                                        "other.stuff.Whatever": {"key": "value"}
                                    },
                                    "python-version": "3.10",
                                },
                            ],
                        },
                    ),
                ],
            ),
            (
                "top",
                [top],
                [
                    RawConfig(
                        top,
                        {
                            "root": True,
                            "enable-root-import": True,
                            "enable": ["more.rules"],
                            "disable": ["fixit.rules.SomethingSpecific"],
                            "python-version": "3.8",
                            "overrides": [
                                {
                                    "path": "other",
                                    "enable": ["other.stuff", ".globalrules"],
                                    "disable": ["fixit.rules"],
                                    "options": {
                                        "other.stuff.Whatever": {"key": "value"}
                                    },
                                    "python-version": "3.10",
                                },
                            ],
                        },
                    ),
                ],
            ),
        ):
            with self.subTest(name):
                actual = config.read_configs(paths)
                self.assertListEqual(expected, actual)

    def test_merge_configs(self):
        root = self.tdp
        target = root / "a" / "b" / "c" / "foo.py"

        for name, raw_configs, expected in (
            (
                "empty",
                [],
                Config(
                    path=target,
                    root=Path(target.anchor),
                    enable=[QualifiedRule("fixit.rules")],
                ),
            ),
            (
                "single",
                [
                    RawConfig(
                        (root / "fixit.toml"),
                        {
                            "enable": ["foo", "bar"],
                            "disable": ["bar"],
                        },
                    ),
                ],
                Config(
                    path=target,
                    root=root,
                    enable=[QualifiedRule("fixit.rules"), QualifiedRule("foo")],
                    disable=[QualifiedRule("bar")],
                ),
            ),
            (
                "without root",
                [
                    RawConfig(
                        (root / "a/b/c/fixit.toml"),
                        {"enable": ["foo"], "python-version": "3.10"},
                    ),
                    RawConfig(
                        (root / "a/b/fixit.toml"),
                        {"enable": ["bar"], "disable": ["foo"]},
                    ),
                    RawConfig(
                        (root / "a/fixit.toml"),
                        {"enable": ["foo"], "python-version": "3.8"},
                    ),
                ],
                Config(
                    path=target,
                    root=(root / "a"),
                    enable=[
                        QualifiedRule("bar"),
                        QualifiedRule("fixit.rules"),
                        QualifiedRule("foo"),
                    ],
                    python_version=Version("3.10"),
                ),
            ),
            (
                "with root",
                [
                    RawConfig(
                        (root / "a/b/c/fixit.toml"),
                        {"enable": ["foo"], "root": True},
                    ),
                    RawConfig(
                        (root / "a/b/fixit.toml"),
                        {},
                    ),
                    RawConfig(
                        (root / "a/fixit.toml"),
                        {},
                    ),
                ],
                Config(
                    path=target,
                    root=(root / "a/b/c"),
                    enable=[QualifiedRule("fixit.rules"), QualifiedRule("foo")],
                ),
            ),
        ):
            with self.subTest(name):
                actual = config.merge_configs(target, raw_configs)
                self.assertEqual(expected, actual)

    def test_generate_config(self):
        for name, path, root, expected in (
            (
                "inner",
                self.inner / "foo.py",
                None,
                Config(
                    path=self.inner / "foo.py",
                    root=self.inner,
                    enable=[
                        QualifiedRule("fake8"),
                        QualifiedRule("fixit.rules"),
                        QualifiedRule("make8"),
                    ],
                    disable=[QualifiedRule("foo.bar")],
                ),
            ),
            (
                "outer",
                self.outer / "foo.py",
                None,
                Config(
                    path=self.outer / "foo.py",
                    root=self.tdp,
                    enable_root_import=True,
                    enable=[
                        QualifiedRule(".localrules", local=".", root=self.outer),
                        QualifiedRule("more.rules"),
                    ],
                    disable=[
                        QualifiedRule("fixit.rules"),
                        QualifiedRule("fixit.rules.SomethingSpecific"),
                    ],
                    python_version=Version("3.8"),
                ),
            ),
            (
                "outer with root",
                self.outer / "foo.py",
                self.outer,
                Config(
                    path=self.outer / "foo.py",
                    root=self.outer,
                    enable=[QualifiedRule(".localrules", local=".", root=self.outer)],
                    disable=[QualifiedRule("fixit.rules")],
                ),
            ),
            (
                "other",
                self.tdp / "other" / "foo.py",
                None,
                Config(
                    path=self.tdp / "other" / "foo.py",
                    root=self.tdp,
                    enable_root_import=True,
                    enable=[
                        QualifiedRule(".globalrules", local=".", root=self.tdp),
                        QualifiedRule("more.rules"),
                        QualifiedRule("other.stuff"),
                    ],
                    disable=[
                        QualifiedRule("fixit.rules"),
                        QualifiedRule("fixit.rules.SomethingSpecific"),
                    ],
                    options={"other.stuff.Whatever": {"key": "value"}},
                    python_version=Version("3.10"),
                ),
            ),
            (
                "root",
                self.tdp / "foo.py",
                None,
                Config(
                    path=self.tdp / "foo.py",
                    root=self.tdp,
                    enable_root_import=True,
                    enable=[QualifiedRule("fixit.rules"), QualifiedRule("more.rules")],
                    disable=[QualifiedRule("fixit.rules.SomethingSpecific")],
                    python_version=Version("3.8"),
                ),
            ),
        ):
            with self.subTest(name):
                actual = config.generate_config(path, root)
                self.assertDictEqual(asdict(expected), asdict(actual))

    def test_invalid_config(self):
        with self.subTest("inner enable-root-import"):
            (self.tdp / "pyproject.toml").write_text("[tool.fixit]\nroot = true\n")
            (self.tdp / "outer" / "pyproject.toml").write_text(
                "[tool.fixit]\nenable-root-import = true\n"
            )

            with self.assertRaisesRegex(config.ConfigError, "enable-root-import"):
                config.generate_config(self.tdp / "outer" / "foo.py")

    def test_collect_rules(self):
        from fixit.rules.avoid_or_in_except import AvoidOrInExceptRule
        from fixit.rules.cls_in_classmethod import UseClsInClassmethodRule
        from fixit.rules.no_namedtuple import NoNamedTupleRule
        from fixit.rules.use_types_from_typing import UseTypesFromTypingRule

        AvoidOrInExceptRule.TAGS = {"exceptions"}
        UseTypesFromTypingRule.TAGS = {"typing"}
        NoNamedTupleRule.TAGS = {"typing", "tuples"}

        def collect_types(cfg):
            return sorted([type(rule) for rule in config.collect_rules(cfg)], key=str)

        with self.subTest("everything"):
            rules = collect_types(
                Config(
                    python_version=None,
                )
            )
            self.assertIn(UseClsInClassmethodRule, rules)
            self.assertIn(UseTypesFromTypingRule, rules)

        with self.subTest("opt-out"):
            rules = collect_types(
                Config(
                    disable=[QualifiedRule("fixit.rules", "UseClsInClassmethodRule")],
                    python_version=None,
                )
            )
            self.assertNotIn(UseClsInClassmethodRule, rules)
            self.assertIn(UseTypesFromTypingRule, rules)

        with self.subTest("opt-in"):
            rules = collect_types(
                Config(
                    enable=[QualifiedRule("fixit.rules", "UseClsInClassmethodRule")],
                    python_version=None,
                )
            )
            self.assertListEqual([UseClsInClassmethodRule], rules)

        with self.subTest("version match"):
            rules = collect_types(
                Config(
                    python_version="3.7",
                )
            )
            self.assertIn(UseTypesFromTypingRule, rules)

        with self.subTest("version mismatch"):
            rules = collect_types(
                Config(
                    python_version="3.10",
                )
            )
            self.assertNotIn(UseTypesFromTypingRule, rules)

        with self.subTest("tag select"):
            rules = collect_types(
                Config(
                    python_version=None,
                    tags=Tags.parse("typing"),
                )
            )
            self.assertListEqual(
                [
                    NoNamedTupleRule,
                    UseTypesFromTypingRule,
                ],
                rules,
            )

        with self.subTest("tag filter"):
            rules = collect_types(
                Config(
                    python_version=None,
                    tags=Tags.parse("^exceptions"),
                )
            )
            self.assertNotIn(AvoidOrInExceptRule, rules)

        with self.subTest("tag select and filter"):
            rules = collect_types(
                Config(
                    python_version=None,
                    tags=Tags.parse("typing,^tuples"),
                )
            )
            self.assertListEqual([UseTypesFromTypingRule], rules)
