# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Usage:
#
#   $ python -m fixit.cli.apply_fix --help
#   $ python -m fixit.cli.apply_fix --rules AvoidOrInExceptRule
#   $ python -m fixit.cli.apply_fix . --rules AvoidOrInExceptRule
import argparse
import itertools
import shutil
import sys
import time
from dataclasses import dataclass
from multiprocessing import Manager
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, List, Mapping, Optional, Sequence

from libcst import ParserSyntaxError, parse_module
from libcst.codemod._cli import invoke_formatter
from libcst.metadata import MetadataWrapper

from fixit.cli import find_files, map_paths
from fixit.cli.args import (
    LintWorkers,
    get_compact_parser,
    get_metadata_cache_parser,
    get_multiprocessing_parser,
    get_paths_parser,
    get_rules_parser,
    get_skip_autoformatter_parser,
    get_skip_ignore_byte_marker_parser,
    get_skip_ignore_comments_parser,
)
from fixit.cli.formatter import LintRuleReportFormatter
from fixit.cli.full_repo_metadata import (
    get_metadata_caches,
    rules_require_metadata_cache,
)
from fixit.cli.utils import print_red
from fixit.common.config import get_lint_config
from fixit.common.report import BaseLintRuleReport
from fixit.common.utils import LintRuleCollectionT
from fixit.rule_lint_engine import (
    LintRuleReportsWithAppliedPatches,
    lint_file_and_apply_patches,
)


if TYPE_CHECKING:
    from libcst.metadata.base_provider import ProviderT

MAX_ITER: int = 100


@dataclass(frozen=True)
class LintOpts:
    rules: LintRuleCollectionT
    use_ignore_byte_markers: bool
    use_ignore_comments: bool
    skip_autoformatter: bool
    formatter: LintRuleReportFormatter
    patched_files_list: Optional[List[str]] = None


class AutofixingLintRuleReportFormatter(LintRuleReportFormatter):
    def _format_header(self, report: BaseLintRuleReport) -> str:
        fixed_str = " [applied fix]" if report.patch is not None else ""
        return f"{super()._format_header(report)}{fixed_str}"


def get_one_patchable_report_for_path(
    path: Path,
    source: bytes,
    rules: LintRuleCollectionT,
    use_ignore_byte_markers: bool,
    use_ignore_comments: bool,
    metadata_cache: Optional[Mapping["ProviderT", object]],
) -> LintRuleReportsWithAppliedPatches:
    cst_wrapper: Optional[MetadataWrapper] = None
    if metadata_cache is not None:
        cst_wrapper = MetadataWrapper(
            parse_module(source),
            True,
            metadata_cache,
        )

    return lint_file_and_apply_patches(
        path,
        source,
        rules=rules,
        use_ignore_byte_markers=use_ignore_byte_markers,
        use_ignore_comments=use_ignore_comments,
        # We will need to regenerate metadata cache every time a patch is applied.
        max_iter=1,
        cst_wrapper=cst_wrapper,
        find_unused_suppressions=True,
    )


def apply_fix_operation(
    path: Path,
    opts: LintOpts,
    metadata_cache: Optional[Mapping["ProviderT", object]] = None,
) -> Iterable[str]:
    with open(path, "rb") as f:
        source = f.read()
    patched_files_list = opts.patched_files_list
    try:
        if patched_files_list is None:
            lint_result = lint_file_and_apply_patches(
                path,
                source,
                rules=opts.rules,
                use_ignore_byte_markers=opts.use_ignore_byte_markers,
                use_ignore_comments=opts.use_ignore_comments,
                find_unused_suppressions=True,
            )
            raw_reports = lint_result.reports
            updated_source = lint_result.patched_source
            if updated_source != source:
                if not opts.skip_autoformatter:
                    # Format the code using the config file's formatter.
                    updated_source = invoke_formatter(
                        get_lint_config().formatter, updated_source
                    )
                with open(path, "wb") as f:
                    f.write(updated_source)
        else:
            lint_result = get_one_patchable_report_for_path(
                path,
                source,
                opts.rules,
                opts.use_ignore_byte_markers,
                opts.use_ignore_comments,
                metadata_cache,
            )
            # Will either be a single patchable report, or a collection of non-patchable reports.
            raw_reports = lint_result.reports
            updated_source = lint_result.patched_source
            if updated_source != source:
                # We don't do any formatting here as it's wasteful. The caller should handle formatting all files at the end.
                with open(path, "wb") as f:
                    f.write(updated_source)

                patched_files_list.append(str(path))
                # Return only the report that was used in the patched source.
                return [next(opts.formatter.format(rr) for rr in raw_reports)]
    except (SyntaxError, ParserSyntaxError) as e:
        print_red(
            f"Encountered the following error while parsing source code in file {path}:"
        )
        print(e)
        return []

    return [opts.formatter.format(rr) for rr in raw_reports]


def call_map_paths_and_print_reports(
    file_paths: Iterable[str],
    opts: LintOpts,
    workers: LintWorkers,
    metadata_caches: Optional[Mapping[str, Mapping["ProviderT", object]]] = None,
) -> int:
    """
    Calls map_paths with `apply_fix_operation`, and the passed in file_paths, opts, workers, metadata_cache.
    Returns the number of reports in the files.
    """
    num_reports = 0
    formatted_reports_iter = itertools.chain.from_iterable(
        map_paths(
            apply_fix_operation,
            file_paths,
            opts,
            workers=workers,
            metadata_caches=metadata_caches,
        )
    )

    for formatted_report in formatted_reports_iter:
        # Reports are yielded as soon as they're available. Stream the output to the
        # terminal.
        print(formatted_report)
        num_reports += 1
    return num_reports


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
            get_metadata_cache_parser(),
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
    use_ignore_byte_markers = args.use_ignore_byte_markers
    use_ignore_comments = args.use_ignore_comments
    skip_autoformatter = args.skip_autoformatter
    formatter = AutofixingLintRuleReportFormatter(width, args.compact)
    workers = args.workers

    # Find files if directory was provided.
    file_paths = tuple(find_files(args.paths))

    if not args.compact:
        print(f"Scanning {len(file_paths)} files")
        print("\n".join(file_paths))
        print()
    start_time = time.time()

    total_reports_count = 0

    if rules_require_metadata_cache(rules):
        touched_files = set()
        next_files = file_paths
        with Manager() as manager:
            # Avoid getting stuck in an infinite loop.
            for _ in range(MAX_ITER):
                if not next_files:
                    break

                patched_files = manager.list()
                metadata_caches = get_metadata_caches(args.cache_timeout, next_files)

                next_files = []
                # opts is a more type-safe version of args that we pass around
                opts = LintOpts(
                    rules=rules,
                    use_ignore_byte_markers=use_ignore_byte_markers,
                    use_ignore_comments=use_ignore_comments,
                    skip_autoformatter=skip_autoformatter,
                    formatter=formatter,
                    patched_files_list=patched_files,
                )
                total_reports_count += call_map_paths_and_print_reports(
                    next_files, opts, workers, metadata_caches
                )
                next_files = list(patched_files)
                touched_files.update(patched_files)

        # Finally, format all the touched files.
        if not skip_autoformatter:
            for path in touched_files:
                with open(path, "rb") as f:
                    source = f.read()
                # Format the code using the config file's formatter.
                formatted_source = invoke_formatter(get_lint_config().formatter, source)
                with open(path, "wb") as f:
                    f.write(formatted_source)

    else:
        # opts is a more type-safe version of args that we pass around
        opts = LintOpts(
            rules=rules,
            use_ignore_byte_markers=use_ignore_byte_markers,
            use_ignore_comments=use_ignore_comments,
            skip_autoformatter=skip_autoformatter,
            formatter=formatter,
        )

        total_reports_count = call_map_paths_and_print_reports(
            file_paths, opts, workers, None
        )

    if not args.compact:
        print()
        print(
            f"Found {total_reports_count} reports in {len(file_paths)} files in "
            + f"{time.time() - start_time :.2f} seconds."
        )

    return 0


def register_subparser(parsers: argparse._SubParsersAction) -> None:
    """Add subparser for `apply_fix` command."""
    apply_fix_parser = parsers.add_parser(
        "apply_fix",
        description=(
            "Runs a lint rule's autofixer over all of over a set of "
            + "files or directories.\n"
            + "\n"
            + "This is similar to the functionality provided by LibCST codemods "
            + "(https://libcst.readthedocs.io/en/latest/codemods_tutorial.html), "
            + "but limited to the small subset of APIs provided by Fixit."
        ),
        help="Apply lint rule fix(s)",
        parents=[
            get_rules_parser(),
            get_metadata_cache_parser(),
            get_paths_parser(),
            get_skip_ignore_comments_parser(),
            get_skip_ignore_byte_marker_parser(),
            get_skip_autoformatter_parser(),
            get_compact_parser(),
            get_multiprocessing_parser(),
        ],
    )

    apply_fix_parser.set_defaults(subparser_fn=_main)


def _main(args: argparse.Namespace) -> None:
    width = shutil.get_terminal_size(fallback=(80, 24)).columns

    rules = args.rules
    use_ignore_byte_markers = args.use_ignore_byte_markers
    use_ignore_comments = args.use_ignore_comments
    skip_autoformatter = args.skip_autoformatter
    formatter = AutofixingLintRuleReportFormatter(width, args.compact)
    workers = args.workers

    # Find files if directory was provided.
    file_paths = tuple(find_files(args.paths))

    if not args.compact:
        print(f"Scanning {len(file_paths)} files")
        print("\n".join(file_paths))
        print()
    start_time = time.time()

    total_reports_count = 0

    if rules_require_metadata_cache(rules):
        touched_files = set()
        next_files = file_paths
        with Manager() as manager:
            # Avoid getting stuck in an infinite loop.
            for _ in range(MAX_ITER):
                if not next_files:
                    break

                patched_files = manager.list()
                metadata_caches = get_metadata_caches(args.cache_timeout, next_files)

                next_files = []
                # opts is a more type-safe version of args that we pass around
                opts = LintOpts(
                    rules=rules,
                    use_ignore_byte_markers=use_ignore_byte_markers,
                    use_ignore_comments=use_ignore_comments,
                    skip_autoformatter=skip_autoformatter,
                    formatter=formatter,
                    patched_files_list=patched_files,
                )
                total_reports_count += call_map_paths_and_print_reports(
                    next_files, opts, workers, metadata_caches
                )
                next_files = list(patched_files)
                touched_files.update(patched_files)

        # Finally, format all the touched files.
        if not skip_autoformatter:
            for path in touched_files:
                with open(path, "rb") as f:
                    source = f.read()
                # Format the code using the config file's formatter.
                formatted_source = invoke_formatter(get_lint_config().formatter, source)
                with open(path, "wb") as f:
                    f.write(formatted_source)

    else:
        # opts is a more type-safe version of args that we pass around
        opts = LintOpts(
            rules=rules,
            use_ignore_byte_markers=use_ignore_byte_markers,
            use_ignore_comments=use_ignore_comments,
            skip_autoformatter=skip_autoformatter,
            formatter=formatter,
        )

        total_reports_count = call_map_paths_and_print_reports(
            file_paths, opts, workers, None
        )

    if not args.compact:
        print()
        print(
            f"Found {total_reports_count} reports in {len(file_paths)} files in "
            + f"{time.time() - start_time :.2f} seconds."
        )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
