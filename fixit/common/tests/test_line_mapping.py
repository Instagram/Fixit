# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import tokenize
from io import BytesIO
from textwrap import dedent
from typing import Mapping

from libcst.testing.utils import UnitTest, data_provider

from fixit.common.line_mapping import LineMappingInfo


class LineMappingInfoTest(UnitTest):
    @data_provider(
        {
            "simple": {
                "code": dedent(
                    """\
                    def fn():
                        ...
                    """
                ),
                "physical_to_logical": {1: 1, 2: 2, 3: 3},
                "next_non_empty_logical_line": {1: 1, 2: 2, 3: 3},
            },
            "comments": {
                "code": dedent(
                    """\
                    # comment with
                    # multiple
                    # lines
                    def fn():
                        # comment
                        ...
                    """
                ),
                "physical_to_logical": {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7},
                "next_non_empty_logical_line": {
                    1: 4,
                    2: 4,
                    3: 4,
                    4: 4,
                    5: 6,
                    6: 6,
                    7: 7,
                },
            },
            "blank_lines": {
                "code": dedent(
                    """\


                    def fn():


                        ...
                    """
                ),
                "physical_to_logical": {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7},
                "next_non_empty_logical_line": {
                    1: 3,
                    2: 3,
                    3: 3,
                    4: 6,
                    5: 6,
                    6: 6,
                    7: 7,
                },
            },
            "line_continuation": {
                "code": dedent(
                    """\
                    value = "abc"
                    value = \\
                        "abcd" + \\
                        "efgh" + \\
                        "ijkl" + \\
                        "mnop"
                    """
                ),
                "physical_to_logical": {1: 1, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 7},
                "next_non_empty_logical_line": {
                    1: 1,
                    2: 2,
                    3: 7,
                    4: 7,
                    5: 7,
                    6: 7,
                    7: 7,
                },
            },
            "multiline_string": {
                "code": dedent(
                    """\
                    value = "abc"
                    value = '''
                        abcd
                        efgh
                        ijkl
                        mnop
                    '''
                    """
                ),
                "physical_to_logical": {1: 1, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2, 8: 8},
                "next_non_empty_logical_line": {
                    1: 1,
                    2: 2,
                    3: 8,
                    4: 8,
                    5: 8,
                    6: 8,
                    7: 8,
                    8: 8,
                },
            },
        }
    )
    def test_line_mapping(
        self,
        *,
        code: str,
        physical_to_logical: Mapping[int, int],
        next_non_empty_logical_line: Mapping[int, int],
    ) -> None:
        tokens = tokenize.tokenize(BytesIO(code.encode("utf-8")).readline)
        result = LineMappingInfo.compute(tokens=tokens)
        self.assertEqual(dict(result.physical_to_logical), dict(physical_to_logical))
        for input, expected in next_non_empty_logical_line.items():
            self.assertEqual(result.get_next_non_empty_logical_line(input), expected)
