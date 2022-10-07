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
from ..types import Config, RawConfig


class ConfigTest(TestCase):
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
                """
            )
        )
        (self.outer / "fixit.toml").write_text(
            dedent(
                """
                [tool.fixit]
                greeting = "big hello"
                """
            )
        )
        (self.inner / "pyproject.toml").write_text(
            dedent(
                """
                [tool.fuzzball]
                """
            )
        )
        (self.inner / "fixit.toml").write_text(
            dedent(
                """
                [tool.fixit]
                root = true
                greeting = "i robot"
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
                [RawConfig(innerA, {"greeting": "i robot", "root": True})],
            ),
            (
                "inner partial",
                [innerB, outer, top],
                [
                    RawConfig(outer, {"greeting": "big hello"}),
                    RawConfig(top, {"root": True}),
                ],
            ),
            (
                "outer",
                [outer, top],
                [
                    RawConfig(outer, {"greeting": "big hello"}),
                    RawConfig(top, {"root": True}),
                ],
            ),
            (
                "top",
                [top],
                [RawConfig(top, {"root": True})],
            ),
        ):
            with self.subTest(name):
                actual = config.read_configs(paths)
                self.assertListEqual(expected, actual)

    def test_merge_configs(self):
        target = Path("foo.py")

        for name, raw_configs, expected in (
            ("empty", [], Config(path=target, root=Path(target.anchor))),
            (
                "single",
                [
                    RawConfig(Path("fixit.toml"), {"greeting": "howdy"}),
                ],
                Config(path=target, root=Path("."), greeting="howdy"),
            ),
            (
                "without root",
                [
                    RawConfig(Path("a/b/c/fixit.toml"), {"greeting": "wonderful"}),
                    RawConfig(Path("a/b/fixit.toml"), {"greeting": "test"}),
                    RawConfig(Path("a/fixit.toml"), {}),
                ],
                Config(path=target, root=Path("a"), greeting="wonderful"),
            ),
            (
                "with root",
                [
                    RawConfig(Path("a/b/c/fixit.toml"), {"greeting": "wonderful"}),
                    RawConfig(
                        Path("a/b/fixit.toml"), {"greeting": "test", "root": True}
                    ),
                    RawConfig(Path("a/fixit.toml"), {}),
                ],
                Config(path=target, root=Path("a/b"), greeting="wonderful"),
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
                Config(path=self.inner / "foo.py", root=self.inner, greeting="i robot"),
            ),
            (
                "outer without root",
                self.outer / "foo.py",
                None,
                Config(path=self.outer / "foo.py", root=self.tdp, greeting="big hello"),
            ),
            (
                "outer with root",
                self.outer / "foo.py",
                self.outer,
                Config(
                    path=self.outer / "foo.py", root=self.outer, greeting="big hello"
                ),
            ),
            (
                "root",
                self.tdp / "foo.py",
                None,
                Config(path=self.tdp / "foo.py", root=self.tdp, greeting="hello"),
            ),
        ):
            with self.subTest(name):
                actual = config.generate_config(path, root)
                self.assertDictEqual(asdict(expected), asdict(actual))
