# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Iterable

from libcst.testing.utils import data_provider, UnitTest

from fixit.common.insert_suppressions import (
    insert_suppressions,
    SuppressionComment,
    SuppressionCommentKind,
)
from fixit.common.utils import dedent_with_lstrip


class InsertSuppressionsTest(UnitTest):
    @data_provider(
        {
            "simple_fixme": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    # lint-fixme: IgnoredRule: Some message
                    def fn():
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=1,
                        code="IgnoredRule",
                        message="Some message",
                    )
                ],
            },
            "simple_ignore": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    # lint-ignore: IgnoredRule: Some message
                    def fn():
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.IGNORE,
                        before_line=1,
                        code="IgnoredRule",
                        message="Some message",
                    )
                ],
            },
            "no_message": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    # lint-fixme: IgnoredRule
                    def fn():
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=1,
                        code="IgnoredRule",
                    )
                ],
            },
            "indented": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    def fn():
                        # lint-fixme: IgnoredRule: Some message
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=2,
                        code="IgnoredRule",
                        message="Some message",
                    )
                ],
            },
            "indented_tabs": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                    \t...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    def fn():
                    \t# lint-fixme: IgnoredRule: Some message
                    \t...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=2,
                        code="IgnoredRule",
                        message="Some message",
                    )
                ],
            },
            "multiple_comments": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    # lint-fixme: IgnoredRule: Some message
                    # lint-fixme: IgnoredRule1: Another message
                    def fn():
                        # lint-fixme: IgnoredRule2: Yet another
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=1,
                        code="IgnoredRule",
                        message="Some message",
                    ),
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=1,
                        code="IgnoredRule1",
                        message="Another message",
                    ),
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=2,
                        code="IgnoredRule2",
                        message="Yet another",
                    ),
                ],
            },
            "multiline_comment": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    def fn():
                        # lint-fixme: IgnoredRule:
                        # lint: Some really long
                        # lint: message that
                        # lint: rambles on and on
                        # lint: that needs to be
                        # lint: wrapped
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=2,
                        code="IgnoredRule",
                        message=(
                            "Some really long message that rambles on and on that "
                            + "needs to be wrapped"
                        ),
                        max_lines=(2**32),
                    )
                ],
                "code_width": 30,
            },
            "newlines_in_message": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    def fn():
                        # lint-fixme: IgnoredRule: This is the first line.
                        # lint: This is a subsequent line followed by a blank line.
                        # lint:
                        # lint: And this is the last line.
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=2,
                        code="IgnoredRule",
                        message=(
                            "This is the first line.\n"
                            + "This is a subsequent line followed by a blank line.\n"
                            + "\n"
                            + "And this is the last line."
                        ),
                        max_lines=(2**32),
                    )
                ],
            },
            "logical_line_continuation": {
                "before": dedent_with_lstrip(
                    """
                    value = "abc"
                    value = \\
                        "abcd" + \\
                        "efgh" + \\
                        "ijkl" + \\
                        "mnop"
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    value = "abc"
                    # lint-fixme: IgnoredRule: Some message
                    value = \\
                        "abcd" + \\
                        "efgh" + \\
                        "ijkl" + \\
                        "mnop"
                    """
                ),
                "comments": [
                    # Line 4 isn't a logical line, so we expect that the comment will
                    # be put on the first logical line above it.
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=4,
                        code="IgnoredRule",
                        message="Some message",
                    )
                ],
            },
            "logical_line_multiline_string": {
                "before": dedent_with_lstrip(
                    """
                    value = "abc"
                    value = '''
                        abcd
                        efgh
                        ijkl
                        mnop
                    '''
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    value = "abc"
                    # lint-fixme: IgnoredRule: Some message
                    value = '''
                        abcd
                        efgh
                        ijkl
                        mnop
                    '''
                    """
                ),
                "comments": [
                    # Line 4 isn't a logical line, so we expect that the comment will
                    # be put on the first logical line above it.
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=4,
                        code="IgnoredRule",
                        message="Some message",
                    )
                ],
            },
            "max_lines_first_block": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    # lint-fixme: IgnoredRule: first block ...
                    def fn():
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=1,
                        code="IgnoredRule",
                        message="first block\n\nsecond block\nthird block",
                        max_lines=1,
                    )
                ],
            },
            "max_lines_between_blocks": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    # lint-fixme: IgnoredRule: first block
                    # lint: ...
                    def fn():
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=1,
                        code="IgnoredRule",
                        message="first block\n\nsecond block\nthird block",
                        max_lines=2,
                    )
                ],
            },
            "max_lines_subsequent_blocks": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    # lint-fixme: IgnoredRule: first block
                    # lint:
                    # lint: second block ...
                    def fn():
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=1,
                        code="IgnoredRule",
                        message="first block\n\nsecond block\nthird block",
                        max_lines=3,
                    )
                ],
            },
            # In this example the last visible line wouldn't normally need to be
            # truncated, but we don't quite have enough space for the "[...]" ellipsis
            # at the end.
            "max_lines_requires_trimming": {
                "before": dedent_with_lstrip(
                    """
                    def fn():
                        ...
                    """
                ),
                "after": dedent_with_lstrip(
                    """
                    # lint-fixme: IgnoredRule: first line
                    # lint: second line which is too ...
                    def fn():
                        ...
                    """
                ),
                "comments": [
                    SuppressionComment(
                        kind=SuppressionCommentKind.FIXME,
                        before_line=1,
                        code="IgnoredRule",
                        message="first line\nsecond line which is too long\nlast line",
                        max_lines=2,
                    )
                ],
                "code_width": 40,  # the truncated comment is 38 characters long (<40)
            },
        }
    )
    def test_insert_suppressions(
        self,
        *,
        before: str,
        after: str,
        comments: Iterable[SuppressionComment],
        code_width: int = 1000,
        min_comment_width: int = 1,
    ) -> None:
        result = insert_suppressions(
            before.encode("utf-8"),
            comments,
            code_width=code_width,
            min_comment_width=min_comment_width,
        )
        updated_source = result.updated_source.decode("utf-8")
        self.assertEqual(updated_source, after)
        self.assertEqual(len(result.failed_insertions), 0)
