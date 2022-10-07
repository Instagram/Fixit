# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
For backwards compatibility.
"""

from fixit.cli.args import (
    get_compact_parser,
    get_multiprocessing_parser,
    get_paths_parser,
    get_rule_parser,
    get_skip_ignore_byte_marker_parser,
    get_use_ignore_comments_parser,
)


__all__ = [
    "get_compact_parser",
    "get_multiprocessing_parser",
    "get_paths_parser",
    "get_rule_parser",
    "get_skip_ignore_byte_marker_parser",
    "get_use_ignore_comments_parser",
]
