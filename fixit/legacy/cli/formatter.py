# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import textwrap
from typing import ClassVar

from fixit.common.report import BaseLintRuleReport


class LintRuleReportFormatter:
    """
    A pretty-printer for BaseLintRuleReport objects.

    The methods in this class can be overridden to tweak the formatting.
    """

    # If your terminal window is narrower than this, we'll give up and just wrap the
    # content to this width instead.
    #
    # This is necessary since some elements (e.g. an indent) have a fixed width.
    MIN_WIDTH: ClassVar[int] = 5
    width: int
    compact: bool

    def __init__(self, width: int, compact: bool = False) -> None:
        self.width = max(width, self.MIN_WIDTH)
        self.compact = compact

    def _format_position(self, report: BaseLintRuleReport) -> str:
        return f"{report.file_path}:{report.line}:{report.column}"

    def _format_header(self, report: BaseLintRuleReport) -> str:
        return self._format_position(report)

    def _format_details_raw(self, report: BaseLintRuleReport) -> str:
        return f"{report.code}: {report.message}"

    def _format_details(self, report: BaseLintRuleReport) -> str:
        lines = self._format_details_raw(report).split("\n")
        wrapped_lines = []
        for line in lines:
            if line == "":
                wrapped_lines.append(line)
            else:
                wrapped_lines.extend(
                    textwrap.wrap(
                        line,
                        self.width,
                        initial_indent=(" " * 4),
                        subsequent_indent=(" " * 4),
                    )
                )
        return "\n".join(wrapped_lines)

    def format(self, report: BaseLintRuleReport) -> str:
        if self.compact:
            return f"{self._format_header(report)}"
        else:
            return f"{self._format_header(report)}\n{self._format_details(report)}"


def format_warning(message: str, width: int, prefix: str = "Warning: ") -> str:
    return "\n".join(
        textwrap.wrap(
            message,
            max(width, len(prefix) + 1),
            initial_indent=prefix,
            subsequent_indent=(" " * len(prefix)),
        )
    )
