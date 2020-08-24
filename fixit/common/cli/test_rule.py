# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Usage:
#
#   $ python -m fixit.common.cli.test_rule --help
#   $ python -m fixit.common.cli.test_rule AvoidOrInExceptRule
#   $ python -m fixit.common.cli.test_rule AvoidOrInExceptRule .

import argparse
import itertools
import shutil
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from logging import Handler, Logger, LogRecord, getLogger
from pathlib import Path
from subprocess import TimeoutExpired
from typing import (
    TYPE_CHECKING,
    DefaultDict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
)

from libcst import ParserSyntaxError, parse_module
from libcst.metadata import MetadataWrapper, TypeInferenceProvider

from fixit.common.base import LintRuleT
from fixit.common.cli import find_files, map_paths
from fixit.common.cli.args import (
    get_compact_parser,
    get_multiprocessing_parser,
    get_paths_parser,
    get_rule_parser,
    get_skip_ignore_byte_marker_parser,
    get_use_ignore_comments_parser,
)
from fixit.common.cli.formatter import LintRuleReportFormatter
from fixit.common.cli.utils import print_red, print_yellow
from fixit.common.full_repo_metadata import FullRepoMetadataConfig, get_repo_caches
from fixit.rule_lint_engine import lint_file


if TYPE_CHECKING:
    from libcst.metadata.base_provider import ProviderT


@dataclass(frozen=True)
class LintOpts:
    rule: LintRuleT
    use_ignore_byte_markers: bool
    use_ignore_comments: bool
    formatter: LintRuleReportFormatter


class CustomMetadataErrorHandler(Handler):
    timeout_paths: List[str] = []
    other_exceptions: DefaultDict[Exception, List[str]] = defaultdict(list)

    def emit(self, record: LogRecord) -> None:
        # According to logging documentation, exc_info will be a tuple of three values: (type, value, traceback)
        # see https://docs.python.org/3.8/library/logging.html#logrecord-objects
        exc_info = record.exc_info
        if exc_info is not None:
            exc_type = exc_info[0]
            failed_paths = record.__dict__.get("paths")
            if exc_type is not None:
                # Store exceptions in memory for processing later.
                if exc_type is TimeoutExpired:
                    self.timeout_paths += failed_paths
                elif exc_type is Exception:
                    self.other_exceptions[exc_type] += failed_paths


def get_metadata_caches(
    rule: LintRuleT, cache_timeout: int, file_paths: Iterable[str]
) -> Optional[Mapping[str, Mapping["ProviderT", object]]]:
    metadata_caches: Optional[Mapping[str, Mapping["ProviderT", object]]] = None
    get_inherited_dependencies = getattr(rule, "get_inherited_dependencies", None)

    if get_inherited_dependencies is None:
        # It is not a MetadataDependent type.
        return
    if TypeInferenceProvider in get_inherited_dependencies():
        logger: Logger = getLogger("Metadata Cache Logger")
        handler = CustomMetadataErrorHandler()
        logger.addHandler(handler)
        full_repo_metadata_config: FullRepoMetadataConfig = FullRepoMetadataConfig(
            providers={TypeInferenceProvider},
            timeout_seconds=cache_timeout,
            batch_size=100,
            logger=logger,
        )
        metadata_caches = get_repo_caches(file_paths, full_repo_metadata_config)
        # Let user know of any cache fetching failures.
        if handler.timeout_paths:
            print(
                "Unable to get metadata cache for the following paths:\n"
                + "\n".join(handler.timeout_paths)
            )
            print_yellow(
                "Try increasing the --cache-timeout value or passing fewer files."
            )
        for exc, failed_paths in handler.other_exceptions.items():
            print(
                f"Encountered {exc} when trying to get metadata for the following paths:\n"
                + "\n".join(failed_paths)
            )
            print_yellow("Perhaps running ```pyre start``` might help?")
    return metadata_caches


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
            rules={opts.rule},
            use_ignore_byte_markers=opts.use_ignore_byte_markers,
            use_ignore_comments=opts.use_ignore_comments,
            cst_wrapper=cst_wrapper,
        )
    except (SyntaxError, ParserSyntaxError) as e:
        print_red(
            f"Encountered the following error while parsing source code in file {path}:"
        )
        print(e)
        return []

    # linter completed successfully
    return [opts.formatter.format(rr) for rr in raw_reports]


def main(raw_args: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validates your lint rule by running it against the specified, "
            + "directory or file. This is not a substitute for unit tests, "
            + "but it can provide additional confidence in your lint rule.\n"
        ),
        parents=[
            get_rule_parser(),
            get_paths_parser(),
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

    if not args.compact:
        print(f"Scanning {len(file_paths)} files")
        print()
    start_time = time.time()

    metadata_caches = get_metadata_caches(args.rule, args.cache_timeout, file_paths)

    # opts is a more type-safe version of args that we pass around
    opts = LintOpts(
        rule=args.rule,
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
    sys.exit(int(bool(formatted_reports)))


# lint-fixme: IG237, NoMainCheckRule: Scripts within IG distillery should be invoked with "igscript" and
# lint: disallow execution by checking for __main__.
# lint: See https://fburl.com/igscript.
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
