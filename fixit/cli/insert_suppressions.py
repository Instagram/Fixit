# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Usage:
#
#   $ python -m fixit.cli.insert_suppressions --help
#   $ python -m fixit.cli.insert_suppressions fixit.rules.avoid_or_in_except.AvoidOrInExceptRule
#   $ python -m fixit.cli.insert_suppressions fixit.rules.avoid_or_in_except.AvoidOrInExceptRule .

import argparse
import itertools
import shutil
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, List, Mapping, Optional, Union

from libcst import ParserSyntaxError, parse_module
from libcst.codemod._cli import invoke_formatter
from libcst.metadata import MetadataWrapper

from fixit.cli import find_files, map_paths
from fixit.cli.args import (
    get_compact_parser,
    get_metadata_cache_parser,
    get_multiprocessing_parser,
    get_paths_parser,
    get_rule_parser,
    get_skip_autoformatter_parser,
)
from fixit.cli.formatter import LintRuleReportFormatter
from fixit.cli.full_repo_metadata import (
    get_metadata_caches,
    rules_require_metadata_cache,
)
from fixit.cli.utils import print_red
from fixit.common.base import LintRuleT
from fixit.common.config import get_lint_config
from fixit.common.insert_suppressions import (
    SuppressionComment,
    SuppressionCommentKind,
    insert_suppressions,
)
from fixit.common.report import BaseLintRuleReport
from fixit.rule_lint_engine import lint_file


if TYPE_CHECKING:
    from libcst.metadata.base_provider import ProviderT

DESCRIPTION: str = """Inserts `# lint-fixme` comments into a file where lint violations
are found. You should only use this tool if it's not feasible to fix the existing
violations."""

PARENTS: List[argparse.ArgumentParser] = [
    get_rule_parser(),
    get_paths_parser(),
    get_skip_autoformatter_parser(),
    get_compact_parser(),
    get_metadata_cache_parser(),
    get_multiprocessing_parser(),
]


class MessageKind(Enum):
    USE_LINT_REPORT = 1
    NO_MESSAGE = 2


@dataclass(frozen=True)
class InsertSuppressionsOpts:
    rule: LintRuleT
    skip_autoformatter: bool
    kind: SuppressionCommentKind
    message: Union[MessageKind, str]
    max_lines: int
    formatter: LintRuleReportFormatter


class SuppressedLintRuleReportFormatter(LintRuleReportFormatter):
    def _format_header(self, report: BaseLintRuleReport) -> str:
        return f"{super()._format_header(report)} [inserted suppression]"


def get_formatted_reports_for_path(
    path: Path,
    opts: InsertSuppressionsOpts,
    metadata_cache: Optional[Mapping["ProviderT", object]] = None,
) -> Iterable[str]:
    with open(path, "rb") as f:
        source = f.read()

    try:
        cst_wrapper = None
        if metadata_cache is not None:
            cst_wrapper = MetadataWrapper(
                parse_module(source),
                True,
                metadata_cache,
            )
        raw_reports = lint_file(
            path, source, rules={opts.rule}, cst_wrapper=cst_wrapper
        )
    except (SyntaxError, ParserSyntaxError) as e:
        print_red(
            f"Encountered the following error while parsing source code in file {path}:"
        )
        print(e)
        return []

    opts_message = opts.message
    comments = []
    for rr in raw_reports:
        if isinstance(opts_message, str):
            message = opts_message
        elif opts_message == MessageKind.USE_LINT_REPORT:
            message = rr.message
        else:  # opts_message == MessageKind.NO_MESSAGE
            message = None
        comments.append(
            SuppressionComment(opts.kind, rr.line, rr.code, message, opts.max_lines)
        )
    insert_suppressions_result = insert_suppressions(source, comments)
    updated_source = insert_suppressions_result.updated_source
    assert (
        not insert_suppressions_result.failed_insertions
    ), "Failed to insert some comments. This should not be possible."

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


def _parser_arguments(
    parser: Union[argparse._SubParsersAction, argparse.ArgumentParser],
    sub_parser: bool = True,
) -> None:
    """All required arguments for `insert_supressions`"""
    parser.add_argument(
        "--kind",
        default="fixme",
        choices=[kind.name.lower() for kind in SuppressionCommentKind],
        help="Should we use `# lint-fixme` or `# lint-ignore`? Defaults to 'fixme'.",
    )
    message_group = parser.add_mutually_exclusive_group()
    message_group.add_argument(
        "--message",
        default=None,
        help="Overrides the lint message used in the fixme comment.",
    )
    message_group.add_argument(
        "--no-message",
        action="store_true",
        help=(
            "Don't include a message with the suppression comment. Only include the "
            + "lint code."
        ),
    )
    parser.add_argument(
        "--max-lines",
        default=3,
        type=int,
        help="The maximum number of lines a comment can span before getting truncated",
    )

    if sub_parser:
        parser.set_defaults(subparser_fn=_main)
    else:
        _main(parser.parse_args())


def register_subparser(parser: argparse._SubParsersAction = None) -> None:
    """Add parser or subparser for `insert_supressions` command."""
    if parser is None:
        insert_supressions_parser = argparse.ArgumentParser(
            description=DESCRIPTION, parents=PARENTS
        )
        _parser_arguments(insert_supressions_parser, sub_parser=False)

    else:
        insert_supressions_parser = parser.add_parser(
            "insert_suppressions",
            description=DESCRIPTION,
            parents=PARENTS,
            help="Insert comments where violations are found",
        )
        _parser_arguments(insert_supressions_parser)


def _main(args: argparse.Namespace) -> None:
    width = shutil.get_terminal_size(fallback=(80, 24)).columns

    # Find files if directory was provided.
    file_paths = tuple(find_files((str(p) for p in args.paths)))

    if not args.compact:
        print(f"Scanning {len(file_paths)} files")
        print()
    start_time = time.time()

    if args.no_message:
        message = MessageKind.NO_MESSAGE
    elif args.message is not None:
        message = args.message
    else:
        message = MessageKind.USE_LINT_REPORT

    metadata_caches: Optional[Mapping[str, Mapping["ProviderT", object]]] = None
    if rules_require_metadata_cache({args.rule}):
        metadata_caches = get_metadata_caches(args.cache_timeout, file_paths)

    # opts is a more type-safe version of args that we pass around
    opts = InsertSuppressionsOpts(
        rule=args.rule,
        skip_autoformatter=args.skip_autoformatter,
        kind=SuppressionCommentKind[args.kind.upper()],
        message=message,
        max_lines=args.max_lines,
        formatter=SuppressedLintRuleReportFormatter(width, args.compact),
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


if __name__ == "__main__":
    register_subparser()
