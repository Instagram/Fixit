# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import importlib
from enum import Enum
from pathlib import Path
from typing import List

from fixit.common.base import LintRuleT
from fixit.common.config import get_lint_config, get_rules_from_config
from fixit.common.utils import (
    LintRuleNotFoundError,
    find_and_import_rule,
    import_distinct_rules_from_package,
)


class FixtureDirNotFoundError(Exception):
    pass


def import_rule(rule_name: str) -> LintRuleT:
    # Using the rule_name or full dotted name, attempt to import the rule.
    rule_module_path, _, rule_class_name = rule_name.rpartition(".")
    if rule_module_path:
        # If user provided a dotted path, we assume it's valid and import the rule directly.
        imported_rule = getattr(
            importlib.import_module(rule_module_path), rule_class_name,
        )
        return imported_rule
    # Otherwise, only a class name was provided, so try to find the rule by searching each package specified in the config.
    return find_and_import_rule(rule_class_name, get_lint_config().packages)


def get_pyre_fixture_dir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--fixture-dir",
        type=(lambda p: Path(p).resolve(strict=True)),
        help=("Main fixture file directory for integration testing."),
        default=get_lint_config().fixture_dir,
    )
    return parser


def get_rules_package_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--rules-package",
        help=("Full dotted path of a package containing lint rules."),
        default="fixit.rules",
    )
    return parser


def get_rule_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "rule",
        type=import_rule,
        help=(
            "The name of your lint rule class or the full dotted path to your lint rule class. "
            + "(e.g. `NoAssertEqualsRule` or `fixit.rules.no_assert_equals.NoAssertEqualsRule`)"
        ),
    )
    return parser


class RuleAction(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: List[str],
        option_string: str,
    ) -> None:
        all_rules = set()
        for rule_or_package in values:
            try:
                # Try to treat as a package first.
                all_rules.update(import_distinct_rules_from_package(rule_or_package))
            except ModuleNotFoundError:
                try:
                    all_rules.add(import_rule(rule_or_package))
                except LintRuleNotFoundError:
                    raise ValueError(
                        f"Unable to import rule or package named {rule_or_package}"
                    )
        setattr(namespace, self.dest, all_rules)


def get_rules_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--rules",
        nargs="*",
        help=(
            "The names of lint rule classes to run, or packages containing lint rules, separated by a space. "
            + "(e.g `--rules NoAssertEqualsRule NoUnnecessaryListComprehensionRule my.custom.package`)"
        ),
        action=RuleAction,
        dest="rules",
        default=get_rules_from_config(),
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
            + "which to run the script. If not specified, the lint rule is run on the"
            + " `repo_root` specified in the `fixit.config.yaml` file."
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


def get_metadata_cache_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--cache-timeout",
        type=int,
        help="Timeout (seconds) for metadata cache fetching. Default is 2 seconds.",
        default=2,
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
