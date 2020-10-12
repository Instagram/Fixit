# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Usage:
#
#   $ python -m fixit.cli.run_rules --help
#   $ python -m fixit.cli.run_rules
#   $ python -m fixit.cli.run_rules --rules AvoidOrInExceptRule
#   $ python -m fixit.cli.run_rules . --rules AvoidOrInExceptRule NoUnnecessaryListComprehensionRule
#   $ python -m fixit.cli.run_rules . --rules AvoidOrInExceptRule my.custom.rules.package
#   $ python -m fixit.cli.run_rules . --rules fixit.rules

import argparse
import itertools
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Mapping, Optional, Sequence

from libcst import ParserSyntaxError, parse_module
from libcst.metadata import MetadataWrapper

from fixit.cli import find_files, map_paths
from fixit.cli.args import (
    get_compact_parser,
    get_multiprocessing_parser,
    get_paths_parser,
    get_rules_parser,
    get_skip_ignore_byte_marker_parser,
    get_use_ignore_comments_parser,
)
from fixit.cli.formatter import LintRuleReportFormatter
from fixit.cli.full_repo_metadata import (
    get_metadata_caches,
    rules_require_metadata_cache,
)
from fixit.cli.utils import print_red
from fixit.common.utils import LintRuleCollectionT
from fixit.rule_lint_engine import lint_file


if TYPE_CHECKING:
    from libcst.metadata.base_provider import ProviderT


@dataclass(frozen=True)
class LintOpts:
    rules: LintRuleCollectionT
    use_ignore_byte_markers: bool
    use_ignore_comments: bool
    formatter: LintRuleReportFormatter


def get_formatted_reports_for_path(
    path: Path,
    opts: LintOpts,
    metadata_cache: Optional[Mapping["ProviderT", object]] = None,
) -> Iterable[str]:
    with open(path, "rb") as f:
        source = f.read()

    try:
        cst_wrapper = None
        if metadata_cache is not None:
            cst_wrapper = MetadataWrapper(parse_module(source), True, metadata_cache)
        raw_reports = lint_file(
            path,
            source,
            rules=opts.rules,
            use_ignore_byte_markers=opts.use_ignore_byte_markers,
            use_ignore_comments=opts.use_ignore_comments,
            cst_wrapper=cst_wrapper,
            find_unused_suppressions=True,
        )
    except (SyntaxError, ParserSyntaxError) as e:
        print_red(
            f"Encountered the following error while parsing source code in file {path}:"
        )
        print(e)
        return []

    # linter completed successfully
    return [opts.formatter.format(rr) for rr in raw_reports]


def main(raw_args: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validates your lint rules by running them against the specified, "
            + "directory or file(s). This is not a substitute for unit tests, "
            + "but it can provide additional confidence in your lint rules.\n"
            + "If no lint rules or packages are specified, runs all lint rules "
            + "found in the packages specified in `fixit.config.yaml`."
        ),
        parents=[
            get_paths_parser(),
            get_rules_parser(),
            get_use_ignore_comments_parser(),
            get_skip_ignore_byte_marker_parser(),
            get_compact_parser(),
            get_multiprocessing_parser(),
        ],
    )

    parser.add_argument(
        "--cache-timeout",
        type=int,
        help="Timeout (seconds) for metadata cache fetching. Default is 2 seconds.",
        default=2,
    )

    args = parser.parse_args(raw_args)
    width = shutil.get_terminal_size(fallback=(80, 24)).columns

    # expand path if it's a directory
    file_paths = tuple(find_files(args.paths))
    all_rules = args.rules

    if not args.compact:
        print(f"Scanning {len(file_paths)} files")
        print(f"Testing {len(all_rules)} rules")
        print()
    start_time = time.time()

    metadata_caches: Optional[Mapping[str, Mapping["ProviderT", object]]] = None
    if rules_require_metadata_cache(all_rules):
        metadata_caches = get_metadata_caches(args.cache_timeout, file_paths)

    # opts is a more type-safe version of args that we pass around
    opts = LintOpts(
        rules=all_rules,
        use_ignore_byte_markers=args.use_ignore_byte_markers,
        use_ignore_comments=args.use_ignore_comments,
        formatter=LintRuleReportFormatter(width, args.compact),
    )

    formatted_reports_iter = itertools.chain.from_iterable(
        map_paths(
            get_formatted_reports_for_path,
            file_paths,
            opts,
            workers=args.workers,
            metadata_caches=metadata_caches,
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

    # Return with an exit code of 1 if there are any violations found.
    return int(bool(formatted_reports))


def register_subparser(parsers: argparse._SubParsersAction) -> None:
    """Add subparser for `run_rules` command."""
    run_rules_parser = parsers.add_parser(
        "run_rules",
        description=(
            "Validates your lint rules by running them against the specified, "
            + "directory or file(s). This is not a substitute for unit tests, "
            + "but it can provide additional confidence in your lint rules.\n"
            + "If no lint rules or packages are specified, runs all lint rules "
            + "found in the packages specified in `fixit.config.yaml`."
        ),
        help="Run fixit rules against python code",
        parents=[
            get_paths_parser(),
            get_rules_parser(),
            get_use_ignore_comments_parser(),
            get_skip_ignore_byte_marker_parser(),
            get_compact_parser(),
            get_multiprocessing_parser(),
        ],
    )

    run_rules_parser.add_argument(
        "--cache-timeout",
        type=int,
        help="Timeout (seconds) for metadata cache fetching. Default is 2 seconds.",
        default=2,
    )

    run_rules_parser.set_defaults(subparser_fn=_main)


def _main(args: argparse.Namespace):
    width = shutil.get_terminal_size(fallback=(80, 24)).columns

    # expand path if it's a directory
    file_paths = tuple(find_files(args.paths))
    all_rules = args.rules

    if not args.compact:
        print(f"Scanning {len(file_paths)} files")
        print(f"Testing {len(all_rules)} rules")
        print()
    start_time = time.time()

    metadata_caches: Optional[Mapping[str, Mapping["ProviderT", object]]] = None
    if rules_require_metadata_cache(all_rules):
        metadata_caches = get_metadata_caches(args.cache_timeout, file_paths)

    # opts is a more type-safe version of args that we pass around
    opts = LintOpts(
        rules=all_rules,
        use_ignore_byte_markers=args.use_ignore_byte_markers,
        use_ignore_comments=args.use_ignore_comments,
        formatter=LintRuleReportFormatter(width, args.compact),
    )

    formatted_reports_iter = itertools.chain.from_iterable(
        map_paths(
            get_formatted_reports_for_path,
            file_paths,
            opts,
            workers=args.workers,
            metadata_caches=metadata_caches,
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

    # Return with an exit code of 1 if there are any violations found.
    return int(bool(formatted_reports))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
