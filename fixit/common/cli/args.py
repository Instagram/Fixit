# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import importlib
from pathlib import Path

from fixit.common.base import LintRuleT
from fixit.common.cli import LintWorkers
from fixit.common.config import REPO_ROOT


def _import_rule(name: str) -> LintRuleT:
    rule_module_name, rule_class_name = name.split(".")
    rule_class = getattr(
        importlib.import_module(f"static_analysis.lint.rules.{rule_module_name}"),
        rule_class_name,
    )
    return rule_class


def get_rule_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "rule",
        type=_import_rule,
        help=(
            "The name of the file (minus the path and extension) and class joined with "
            + "a '.' that defines your lint rule in static_analysis/lint/rules/*.py. "
            + "(e.g. no_asserts.NoAssertsLintRule)"
        ),
    )
    return parser


def get_paths_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "paths",
        nargs="*",
        type=(lambda p: Path(p).resolve(strict=True)),
        default=(REPO_ROOT / "distillery",),
        help=(
            "The name of a directory (e.g. media) or file (e.g. media/views.py) on "
            + "which to run the lint rule. "
            + "If not specified the lint rule is run on all of distillery."
        ),
    )
    return parser


def get_use_ignore_comments_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--use-ignore-comments",
        action="store_true",
        help="Obey `# noqa`, `# lint-fixme` and `# lint-ignore` comments.",
    )
    return parser


def get_skip_ignore_comments_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--skip-ignore-comments",
        dest="use_ignore_comments",
        action="store_false",
        help="Ignore `# noqa`, `# lint-fixme` and `# lint-ignore` comments.",
    )
    return parser


def get_skip_ignore_byte_marker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--skip-ignore-byte-markers",
        dest="use_ignore_byte_markers",
        action="store_false",
        help=f"Ignore `@gen{''}erated` and `@no{''}lint` markers in files.",
    )
    return parser


def get_compact_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--compact",
        action="store_true",
        help=(
            "Use a compact output that omits the message. This should be easier for "
            + "other scripts to parse."
        ),
    )
    return parser


def get_skip_autoformatter_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--skip-autoformatter",
        action="store_true",
        help=(
            "Skips the autoformatter (e.g. Black) that's normally run after changes "
            + "are applied."
        ),
    )
    return parser


def get_multiprocessing_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--no-multi",
        dest="workers",
        action="store_const",
        const=LintWorkers.USE_CURRENT_THREAD,
        default=LintWorkers.CPU_COUNT,
        help="Run the lint rule with multiprocessing disabled.",
    )
    return parser
