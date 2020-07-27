# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import importlib
from enum import Enum
from pathlib import Path

from fixit.common.base import LintRuleT
from fixit.common.config import get_lint_config


class FixtureDirNotFoundError(Exception):
    pass


def _import_rule(path_to_rule_class: str) -> LintRuleT:
    rule_module_path, rule_class_name = path_to_rule_class.rsplit(".", 1)
    rule_class = getattr(importlib.import_module(rule_module_path), rule_class_name,)
    return rule_class


def get_pyre_fixture_dir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--fixture_dir",
        type=(lambda p: Path(p).resolve(strict=True)),
        help=("Main fixture file directory for Pyre integration testing."),
        default=get_lint_config().fixture_dir,
    )
    return parser


def get_rules_package_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--rules_package", help=("Main package for lint rules."), default="fixit.rules",
    )
    return parser


def get_rule_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "rule",
        type=_import_rule,
        help=(
            "The full name of the module and class joined with "
            + "a '.' that defines your lint rule. "
            + "(e.g. fixit.rules.no_assert_equals.NoAssertEqualsRule)"
        ),
    )
    return parser


def get_paths_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "paths",
        nargs="*",
        type=(lambda p: Path(p).resolve(strict=True)),
        default=(get_lint_config().repo_root,),
        help=(
            "The name of a directory (e.g. media) or file (e.g. media/views.py) on "
            + "which to run the lint rule. "
            + "If not specified the lint rule is run on the `repo_root` specified in Fixit's config file."
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


class LintWorkers(Enum):
    # Spawn (up to) one worker process per CPU core
    CPU_COUNT = "cpu_count"
    # Disable the process pool, and compute results in the current thread and process.
    #
    # This can be useful for debugging, where the process pool may break tracebacks,
    # debuggers, or profilers.
    USE_CURRENT_THREAD = "use_current_thread"


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
