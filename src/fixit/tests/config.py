# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import List, Sequence, Tuple, Type
from unittest import TestCase

from click.testing import CliRunner

from .. import config

from ..cli import main
from ..ftypes import Config, QualifiedRule, RawConfig, Tags, Version
from ..rule import LintRule


class ConfigTest(TestCase):
    maxDiff = None

    def setUp(self) -> None:
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

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_locate_configs(self) -> None:
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

    def test_read_configs(self) -> None:
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

    def test_merge_configs(self) -> None:
        root = self.tdp
        target = root / "a" / "b" / "c" / "foo.py"

        params: Sequence[Tuple[str, List[RawConfig], Config]] = (
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
        )
        for name, raw_configs, expected in params:
            with self.subTest(name):
                actual = config.merge_configs(target, raw_configs)
                self.assertEqual(expected, actual)

    def test_generate_config(self) -> None:
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

    def test_invalid_config(self) -> None:
        with self.subTest("inner enable-root-import"):
            (self.tdp / "pyproject.toml").write_text("[tool.fixit]\nroot = true\n")
            (self.tdp / "outer" / "pyproject.toml").write_text(
                "[tool.fixit]\nenable-root-import = true\n"
            )

            with self.assertRaisesRegex(config.ConfigError, "enable-root-import"):
                config.generate_config(self.tdp / "outer" / "foo.py")

        with self.subTest("inner output-format"):
            (self.tdp / "pyproject.toml").write_text("[tool.fixit]\nroot = true\n")
            (self.tdp / "outer" / "pyproject.toml").write_text(
                "[tool.fixit]\noutput-format = 'this is some weird format'\n"
            )

            with self.assertRaisesRegex(config.ConfigError, "output-format"):
                config.generate_config(self.tdp / "outer" / "foo.py")

    def test_collect_rules(self) -> None:
        from fixit.rules.avoid_or_in_except import AvoidOrInExcept
        from fixit.rules.cls_in_classmethod import UseClsInClassmethod
        from fixit.rules.no_namedtuple import NoNamedTuple
        from fixit.rules.use_types_from_typing import UseTypesFromTyping

        AvoidOrInExcept.TAGS = {"exceptions"}
        UseTypesFromTyping.TAGS = {"typing"}
        NoNamedTuple.TAGS = {"typing", "tuples"}

        def collect_types(cfg: Config) -> List[Type[LintRule]]:
            return sorted([type(rule) for rule in config.collect_rules(cfg)], key=str)

        with self.subTest("everything"):
            rules = collect_types(
                Config(
                    python_version=None,
                )
            )
            self.assertIn(UseClsInClassmethod, rules)
            self.assertIn(UseTypesFromTyping, rules)

        with self.subTest("opt-out"):
            rules = collect_types(
                Config(
                    disable=[QualifiedRule("fixit.rules", "UseClsInClassmethod")],
                    python_version=None,
                )
            )
            self.assertNotIn(UseClsInClassmethod, rules)
            self.assertIn(UseTypesFromTyping, rules)

        with self.subTest("opt-in"):
            rules = collect_types(
                Config(
                    enable=[QualifiedRule("fixit.rules", "UseClsInClassmethod")],
                    python_version=None,
                )
            )
            self.assertListEqual([UseClsInClassmethod], rules)

        with self.subTest("disable builtins"):
            rules = collect_types(
                Config(
                    disable=[QualifiedRule("fixit.rules")],
                    python_version=None,
                )
            )
            self.assertListEqual([], rules)

        with self.subTest("override broad opt-out"):
            rules = collect_types(
                Config(
                    disable=[QualifiedRule("fixit.rules")],
                    enable=[QualifiedRule("fixit.rules", "UseClsInClassmethod")],
                )
            )
            self.assertListEqual([UseClsInClassmethod], rules)

        with self.subTest("version match"):
            rules = collect_types(
                Config(
                    python_version=Version("3.7"),
                )
            )
            self.assertIn(UseTypesFromTyping, rules)

        with self.subTest("version mismatch"):
            rules = collect_types(
                Config(
                    python_version=Version("3.10"),
                )
            )
            self.assertNotIn(UseTypesFromTyping, rules)

        with self.subTest("tag select"):
            rules = collect_types(
                Config(
                    python_version=None,
                    tags=Tags.parse("typing"),
                )
            )
            self.assertListEqual(
                [
                    NoNamedTuple,
                    UseTypesFromTyping,
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
            self.assertNotIn(AvoidOrInExcept, rules)

        with self.subTest("tag select and filter"):
            rules = collect_types(
                Config(
                    python_version=None,
                    tags=Tags.parse("typing,^tuples"),
                )
            )
            self.assertListEqual([UseTypesFromTyping], rules)

    def test_format_output(self):
        expected_format = config.DEFAULT_OUTPUT_FORMAT.replace("@", ":")
        (self.tdp / "pyproject.toml").write_text(
            f"[tool.fixit]\noutput-format = '{expected_format}'\nroot= true\n"
        )
        with self.subTest("output-format loaded correctly"):

            config_ = config.generate_config(self.tdp / "outer" / "foo.py")
            self.assertEqual(
                expected_format,
                config_.output_format,
                (expected_format, config_.output_format),
            )

        runner = CliRunner(mix_stderr=False)
        content = "name = '{name}'.format(name='Jane Doe')"
        filepath = self.tdp / "f_string.py"
        filepath.write_text(content)
        output_format_regex = r".*f_string\.py:\d+:\d+ UseFstring: .+"

        with self.subTest("linting"):
            result = runner.invoke(
                main, ["lint", filepath.as_posix()], catch_exceptions=False
            )
            self.assertRegex(result.output, output_format_regex)

        with self.subTest("linting"):
            result = runner.invoke(
                main, ["fix", filepath.as_posix()], catch_exceptions=False
            )
            self.assertRegex(result.output, output_format_regex)
