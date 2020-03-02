# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import tokenize
from bisect import bisect_left
from dataclasses import dataclass
from typing import Container, Iterable, Mapping, Optional, Sequence

_LOGICAL_LINE_END_MARKERS: Container[int] = (
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.ENDMARKER,
)
_EMPTY_TOKENS: Container[int] = (
    tokenize.ENCODING,
    tokenize.COMMENT,
    tokenize.INDENT,
    tokenize.DEDENT,
)


@dataclass(frozen=True)
class LineMappingInfo:
    """
    Stores the relationship between physical lines (lines separated by a newline) and
    logical lines (lines connected by line continuation characters or multiline tokens).
    Line numbers are one-indexed.

    Because comments can only exist on or above logical lines (you can't have a comment
    between line continuation characters or inside multiline strings), the linter
    converts physical line numbers to logical line numbers before checking that a
    `# lint-fixme` or `# noqa` comment applies to the line.

    Terminology
    -----------

    Physical Line:
        A line separated by newline characters.
    Logical Line:
        A grouping of physical lines. A logical line always has space for exactly one
        trailing comment.
    Non-Empty Logical Line:
        A logical line that isn't just whitespace or comments. When we encounter a
        `# lint-fixme` comment, we need to map it back to the next non-empty logical
        line, since that's what it likely refers to.
    """

    # A many-to-one mapping (1-indexed)
    physical_to_logical: Mapping[int, int]
    # A sorted list of logical lines that have "real" code on them
    non_empty_logical_lines: Sequence[int]

    def get_next_non_empty_logical_line(self, starting_line: int) -> Optional[int]:
        haystack = self.non_empty_logical_lines
        idx = bisect_left(haystack, starting_line)
        if idx == len(haystack):
            return None
        return haystack[idx]

    @staticmethod
    def compute(*, tokens: Iterable[tokenize.TokenInfo]) -> "LineMappingInfo":
        physical_to_logical = {}
        non_empty_logical_lines = []
        has_content = False
        logical_line_start = 1

        for tok in tokens:
            tok_line = tok.start[0]

            if tok.type in _LOGICAL_LINE_END_MARKERS:
                logical_line_end = tok_line
                physical_lines = range(logical_line_start, logical_line_end + 1)
                for pl in physical_lines:
                    physical_to_logical[pl] = logical_line_start
                if has_content or tok.type == tokenize.ENDMARKER:
                    non_empty_logical_lines.append(logical_line_start)
                has_content = False
                logical_line_start = logical_line_end + 1
            elif not has_content and tok.type not in _EMPTY_TOKENS:
                has_content = True

        return LineMappingInfo(physical_to_logical, non_empty_logical_lines)
