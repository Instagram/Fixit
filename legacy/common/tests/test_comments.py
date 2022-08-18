# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import tokenize
from io import BytesIO

from libcst.testing.utils import UnitTest

from fixit.common.comments import CommentInfo
from fixit.common.utils import dedent_with_lstrip


class CommentInfoTest(UnitTest):
    def test_comment_info(self) -> None:
        # A comment on a line with no other leading tokens is a "comment on own line".
        # In contrast, trailing comments come after other tokens on the same line.
        code = dedent_with_lstrip(
            """
            # comment on own line
            # this is a
            # multiline comment
            def fn():
                # comment on own line
                fn2()
                fn3()  # trailing comment
                fn4()
                # comment on own line
            """
        )
        tokens = tokenize.tokenize(BytesIO(code.encode("utf-8")).readline)
        result = CommentInfo.compute(tokens=tokens)
        # The set of all comments includes both comments on their own line and trailing
        # comments.
        self.assertEqual([tok.start[0] for tok in result.comments], [1, 2, 3, 5, 7, 9])
        # `comments_on_own_line` is a subset of all comments
        self.assertEqual(
            [tok.start[0] for tok in result.comments_on_own_line], [1, 2, 3, 5, 9]
        )
