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
from ..ftypes import Config, QualifiedRule, RawConfig


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
                enable = ["main.rules", "more.rules"]
                disable = ["main.rules.SomethingSpecific"]

                [[tool.fixit.overrides]]
                path = "other"
                enable = ["other.stuff"]
                disable = ["main.rules"]
                options = {"other.stuff.Whatever"={key="value"}}
                """
            )
        )
        (self.outer / "fixit.toml").write_text(
            dedent(
                """
                [tool.fixit]
                enable = [".localrules"]
                disable = ["main.rules"]
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
                [self.outer / "fixit.toml", self.tdp / "pyproject.toml"],
            ),
            (
                "outer file",
                self.outer / "frob.py",
                None,
                [self.outer / "fixit.toml", self.tdp / "pyproject.toml"],
            ),
            (
                "inner",
                self.inner,
                None,
                [
                    self.inner / "fixit.toml",
                    self.inner / "pyproject.toml",
                    self.outer / "fixit.toml",
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
                    self.outer / "fixit.toml",
                    self.tdp / "pyproject.toml",
                ],
            ),
            ("outer from outer", self.outer, self.outer, [self.outer / "fixit.toml"]),
            (
                "inner from outer",
                self.inner,
                self.outer,
                [
                    self.inner / "fixit.toml",
                    self.inner / "pyproject.toml",
                    self.outer / "fixit.toml",
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
        outer = self.outer / "fixit.toml"
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
                        outer, {"enable": [".localrules"], "disable": ["main.rules"]}
                    ),
                    RawConfig(
                        top,
                        {
                            "root": True,
                            "enable": ["main.rules", "more.rules"],
                            "disable": ["main.rules.SomethingSpecific"],
                            "overrides": [
                                {
                                    "path": "other",
                                    "enable": ["other.stuff"],
                                    "disable": ["main.rules"],
                                    "options": {
                                        "other.stuff.Whatever": {"key": "value"}
                                    },
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
                        outer, {"enable": [".localrules"], "disable": ["main.rules"]}
                    ),
                    RawConfig(
                        top,
                        {
                            "root": True,
                            "enable": ["main.rules", "more.rules"],
                            "disable": ["main.rules.SomethingSpecific"],
                            "overrides": [
                                {
                                    "path": "other",
                                    "enable": ["other.stuff"],
                                    "disable": ["main.rules"],
                                    "options": {
                                        "other.stuff.Whatever": {"key": "value"}
                                    },
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
                            "enable": ["main.rules", "more.rules"],
                            "disable": ["main.rules.SomethingSpecific"],
                            "overrides": [
                                {
                                    "path": "other",
                                    "enable": ["other.stuff"],
                                    "disable": ["main.rules"],
                                    "options": {
                                        "other.stuff.Whatever": {"key": "value"}
                                    },
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
                        {"enable": ["foo", "bar"], "disable": ["bar"]},
                    ),
                ],
                Config(
                    path=target,
                    root=root,
                    enable=[QualifiedRule("foo")],
                    disable=[QualifiedRule("bar")],
                ),
            ),
            (
                "without root",
                [
                    RawConfig((root / "a/b/c/fixit.toml"), {"enable": ["foo"]}),
                    RawConfig(
                        (root / "a/b/fixit.toml"),
                        {"enable": ["bar"], "disable": ["foo"]},
                    ),
                    RawConfig((root / "a/fixit.toml"), {"enable": ["foo"]}),
                ],
                Config(
                    path=target,
                    root=(root / "a"),
                    enable=[QualifiedRule("bar"), QualifiedRule("foo")],
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
                    path=target, root=(root / "a/b/c"), enable=[QualifiedRule("foo")]
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
                    enable=[QualifiedRule("fake8"), QualifiedRule("make8")],
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
                    enable=[
                        QualifiedRule("localrules", local=".", root=self.outer),
                        QualifiedRule("more.rules"),
                    ],
                    disable=[
                        QualifiedRule("main.rules"),
                        QualifiedRule("main.rules.SomethingSpecific"),
                    ],
                ),
            ),
            (
                "outer with root",
                self.outer / "foo.py",
                self.outer,
                Config(
                    path=self.outer / "foo.py",
                    root=self.outer,
                    enable=[QualifiedRule("localrules", local=".", root=self.outer)],
                    disable=[QualifiedRule("main.rules")],
                ),
            ),
            (
                "other",
                self.tdp / "other" / "foo.py",
                None,
                Config(
                    path=self.tdp / "other" / "foo.py",
                    root=self.tdp,
                    enable=[QualifiedRule("more.rules"), QualifiedRule("other.stuff")],
                    disable=[
                        QualifiedRule("main.rules"),
                        QualifiedRule("main.rules.SomethingSpecific"),
                    ],
                    options={"other.stuff.Whatever": {"key": "value"}},
                ),
            ),
            (
                "root",
                self.tdp / "foo.py",
                None,
                Config(
                    path=self.tdp / "foo.py",
                    root=self.tdp,
                    enable=[QualifiedRule("main.rules"), QualifiedRule("more.rules")],
                    disable=[QualifiedRule("main.rules.SomethingSpecific")],
                ),
            ),
        ):
            with self.subTest(name):
                actual = config.generate_config(path, root)
                self.assertDictEqual(asdict(expected), asdict(actual))
