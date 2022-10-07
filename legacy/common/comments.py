# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import tokenize
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class CommentInfo:

    # All comment tokens. A superset of `comments_on_own_line`. These may be trailing
    # comments, meaning that they come after other non-whitespace content on the same
    # line.
    comments: Sequence[tokenize.TokenInfo]

    # A comment on a line with no other leading tokens is a "comment on own line". This
    # is a subset of all of the comments.
    comments_on_own_line: Sequence[tokenize.TokenInfo]

    @staticmethod
    def compute(*, tokens: Iterable[tokenize.TokenInfo]) -> "CommentInfo":
        comments = []
        comments_on_own_line = []
        prev_tok = None
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                comments.append(tok)
                # Find comments on a line by themselves
                # https://gitlab.com/pycqa/flake8/merge_requests/219
                #
                # We need to check the previous token, but there's no need to check for
                # the next token, since a comment is always the last thing on a given
                # line.
                if prev_tok is None or prev_tok.end[0] != tok.start[0]:
                    comments_on_own_line.append(tok)
            prev_tok = tok
        return CommentInfo(comments, comments_on_own_line)
