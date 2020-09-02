# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Usage:
#
#   $ python -m fixit.cli.apply_fix --help
#   $ python -m fixit.cli.apply_fix fixit.rules.avoid_or_in_except.AvoidOrInExceptRule
#   $ python -m fixit.cli.apply_fix fixit.rules.avoid_or_in_except.AvoidOrInExceptRule .
import argparse
import itertools
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from libcst import ParserSyntaxError
from libcst.codemod._cli import invoke_formatter

from fixit.cli import find_files, map_paths
from fixit.cli.args import (
    get_compact_parser,
    get_multiprocessing_parser,
    get_paths_parser,
    get_rules_parser,
    get_skip_autoformatter_parser,
    get_skip_ignore_byte_marker_parser,
    get_skip_ignore_comments_parser,
)
from fixit.cli.formatter import LintRuleReportFormatter
from fixit.cli.utils import print_red, print_yellow
from fixit.common.base import CstLintRule
from fixit.common.config import get_lint_config
from fixit.common.report import BaseLintRuleReport
from fixit.common.utils import LintRuleCollectionT
from fixit.rule_lint_engine import lint_file_and_apply_patches


@dataclass(frozen=True)
class LintOpts:
    rules: LintRuleCollectionT
    use_ignore_byte_markers: bool
    use_ignore_comments: bool
    skip_autoformatter: bool
    formatter: LintRuleReportFormatter


class AutofixingLintRuleReportFormatter(LintRuleReportFormatter):
    def _format_header(self, report: BaseLintRuleReport) -> str:
        fixed_str = " [applied fix]" if report.patch is not None else ""
        return f"{super()._format_header(report)}{fixed_str}"


def get_formatted_reports_for_path(
    path: Path, opts: LintOpts, _=None,
) -> Iterable[str]:
    with open(path, "rb") as f:
        source = f.read()

    try:
        lint_result = lint_file_and_apply_patches(
            path,
            source,
            rules=opts.rules,
            use_ignore_byte_markers=opts.use_ignore_byte_markers,
            use_ignore_comments=opts.use_ignore_comments,
        )
        raw_reports = lint_result.reports
        updated_source = lint_result.patched_source
    except (SyntaxError, ParserSyntaxError) as e:
        print_red(
            f"Encountered the following error while parsing source code in file {path}:"
        )
        print(e)
        return []

    if updated_source != source:
        if not opts.skip_autoformatter:
            # Format the code using the config file's formatter.
            updated_source = invoke_formatter(
                get_lint_config().formatter, updated_source
            )
        with open(path, "wb") as f:
            f.write(updated_source)

    # linter completed successfully
    return [opts.formatter.format(rr) for rr in raw_reports]


def main(raw_args: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Runs a lint rule's autofixer over all of over a set of "
            + "files or directories.\n"
            + "\n"
            + "This is similar to the functionality provided by LibCST codemods "
            + "(https://libcst.readthedocs.io/en/latest/codemods_tutorial.html), "
            + "but limited to the small subset of APIs provided by Fixit."
        ),
        parents=[
            get_rules_parser(),
            get_paths_parser(),
            get_skip_ignore_comments_parser(),
            get_skip_ignore_byte_marker_parser(),
            get_skip_autoformatter_parser(),
            get_compact_parser(),
            get_multiprocessing_parser(),
        ],
    )

    args = parser.parse_args(raw_args)
    width = shutil.get_terminal_size(fallback=(80, 24)).columns

    rules = args.rules
    # TODO `lint_file_and_apply_patches` cannot handle metadata_caches just yet, so we skip
    # rules that require these caches for now.
    require_metadata_rules = set()
    non_metadata_rules = set()

    for r in rules:
        if issubclass(r, CstLintRule) and getattr(r, "requires_metadata_caches")():
            require_metadata_rules.add(r)
        else:
            non_metadata_rules.add(r)
    if require_metadata_rules:
        print_red("Cannot run `apply_fix` with rules that requires metadata cache:")
        print(",\n".join([r.__name__ for r in require_metadata_rules]))
        if not non_metadata_rules:
            return 1
        print_yellow("Skipping those rules.")

    # Find files if directory was provided.
    file_paths = tuple(find_files((str(p) for p in args.paths)))

    if not args.compact:
        print(f"Scanning {len(file_paths)} files")
        print("\n".join(file_paths))
        print()
    start_time = time.time()

    # opts is a more type-safe version of args that we pass around
    opts = LintOpts(
        rules=non_metadata_rules,
        use_ignore_byte_markers=args.use_ignore_byte_markers,
        use_ignore_comments=args.use_ignore_comments,
        skip_autoformatter=args.skip_autoformatter,
        formatter=AutofixingLintRuleReportFormatter(width, args.compact),
    )

    formatted_reports_iter = itertools.chain.from_iterable(
        map_paths(
            get_formatted_reports_for_path, file_paths, opts, workers=args.workers,
        )
    )

    formatted_reports = []
    for formatted_report in formatted_reports_iter:
        # Reports are yielded as soon as they're available. Stream the output to the
        # terminal.
        print(formatted_report)
        # save the report from the iterator for later use
        formatted_reports.append(formatted_report)

    if not args.compact:
        print()
        print(
            f"Found {len(formatted_reports)} reports in {len(file_paths)} files in "
            + f"{time.time() - start_time :.2f} seconds."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
