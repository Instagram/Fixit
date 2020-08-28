# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
import textwrap
import tokenize
from collections import deque
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Iterable, Mapping, Optional, Sequence

from fixit.common.line_mapping import LineMappingInfo


BODY_PREFIX = "# lint:"
BODY_PREFIX_WITH_SPACE = f"{BODY_PREFIX} "
MAX_LINES_PLACEHOLDER = " ..."
DEFAULT_CODE_WIDTH = 88
DEFAULT_MIN_COMMENT_WIDTH = 40


class SuppressionCommentKind(Enum):
    IGNORE = "lint-ignore"
    FIXME = "lint-fixme"


@dataclass(frozen=True, order=True)
class SuppressionComment:
    """
    Represents a `# lint-fixme` or `# lint-ignore` comment that prevents the linter from
    firing on the subsequent line. If the `message` is too long, the comment is wrapped
    to fill multiple lines.

    Wrapped lines are prefixed with `# lint:`, which allows us to figure out where a
    suppression comment starts and ends, so we can automate removal of unused multiline
    comments.

    At some point in the future, we may extend this to support `# lint-ignore` comments
    too.
    """

    kind: SuppressionCommentKind
    before_line: int  # 1-indexed
    code: str
    message: Optional[str] = None
    max_lines: int = 3

    def to_lines(self, width: int = DEFAULT_MIN_COMMENT_WIDTH) -> Sequence[str]:
        message = self.message
        if message is None:
            return [f"# {self.kind.value}: {self.code}"]

        # chunk the message up splitting by newlines
        raw_message_lines = message.split("\n")
        initial_indent = f"# {self.kind.value}: {self.code}"

        lines = []
        lines.extend(
            textwrap.wrap(
                ": " + raw_message_lines[0],
                initial_indent=initial_indent,
                # We don't want a weirdly formed comment with the first line being
                # longer than the rest.
                width=max(len(initial_indent), width),
                subsequent_indent=BODY_PREFIX_WITH_SPACE,
                drop_whitespace=True,
            )
        )
        # textwrap replaces newlines (`\n`) with a space. This isn't the behavior we
        # want, so we need to wrap each line independently.
        for rml in raw_message_lines[1:]:
            if rml == "":
                lines.append(BODY_PREFIX)
            else:
                lines.extend(
                    textwrap.wrap(
                        rml,
                        width=width,
                        initial_indent=BODY_PREFIX_WITH_SPACE,
                        subsequent_indent=BODY_PREFIX_WITH_SPACE,
                    )
                )

        # Unfortunately our custom handling of newlines also means that we can't use
        # textwrap's `max_lines` and `placeholder` features, and we have to do it
        # ourselves.
        if len(lines) > self.max_lines:
            lines = lines[: self.max_lines]
            last_line = lines[-1]
            # keep removing words from the end until we have room for our placeholder
            while last_line and len(last_line) > (width - len(MAX_LINES_PLACEHOLDER)):
                # this must remove at least one character each time, otherwise we could
                # get stuck in an infinite loop
                last_line = re.sub(r"(\s*\S+|\s+)\Z", "", last_line)
            # if we removed too much, add the `# lint:` prefix back
            if len(last_line) < len(BODY_PREFIX):
                last_line = BODY_PREFIX
            last_line += MAX_LINES_PLACEHOLDER
            lines[-1] = last_line

        return lines


@dataclass(frozen=True)
class InsertSuppressionsResult:
    # An updated sequence of lines with included newlines. These lines can be joined to
    # generate the resulting source code.
    updated_source: bytes
    # It may not be possible to insert a comment where one was needed (e.g. we can't
    # insert a comment inside a multiline string). In those cases, we need to mark these
    # attempted insertions as failures.
    failed_insertions: Sequence[SuppressionComment]


def _get_indentations(tokens: Iterable[tokenize.TokenInfo]) -> Mapping[int, str]:
    """
    Maps logical lines to their indentations.

    This only works for logical lines because logical lines are the only lines with
    measurable indentation.
    """

    result = {}
    # We're 1-indexed, so 0 isn't a real line. The ENCODING dummy token uses it, but we
    # want to skip ENCODING.
    prev_line = 0
    for tok in tokens:
        if tok.type in (tokenize.INDENT, tokenize.DEDENT):
            # These dummy tokens have the wrong start column and always exist alongside
            # a non-dummy token. Skip them.
            continue
        # we only want to know about the first token on each unique line
        if tok.start[0] != prev_line:
            result[tok.start[0]] = tok.line[: tok.start[1]]
            prev_line = tok.start[0]
    return result


def insert_suppressions(
    source: bytes,
    comments: Iterable[SuppressionComment],
    *,
    code_width: int = DEFAULT_CODE_WIDTH,
    min_comment_width: int = DEFAULT_MIN_COMMENT_WIDTH,
) -> InsertSuppressionsResult:
    """
    Given an iterable of `lines`, forms a new sequence of lines with `comments`
    inserted.
    """
    encoding = tokenize.detect_encoding(BytesIO(source).readline)[0]
    tokens = tuple(tokenize.tokenize(BytesIO(source).readline))
    indentations = _get_indentations(tokens)
    physical_to_logical = LineMappingInfo.compute(tokens=tokens).physical_to_logical
    comments_queue = deque(sorted(comments))  # sort by line number
    updated_lines = []

    for line_number, line_bytes in enumerate(BytesIO(source).readlines(), start=1):
        while comments_queue:
            target_line = physical_to_logical[comments_queue[0].before_line]
            if target_line == line_number:
                indent = indentations[line_number]
                width = max(code_width - len(indent), min_comment_width)
                for line in comments_queue.popleft().to_lines(width):
                    updated_lines.append(f"{indent}{line}\n".encode(encoding))
            else:
                break
        updated_lines.append(line_bytes)

    return InsertSuppressionsResult(
        updated_source=b"".join(updated_lines), failed_insertions=tuple(comments_queue)
    )
