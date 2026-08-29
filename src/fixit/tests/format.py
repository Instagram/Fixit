# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path
from unittest import TestCase

import libcst

from ..format import format_module
from ..ftypes import Config

FAKE_PATH = Path("fake.py")


class FormatTest(TestCase):
    def test_black_already_formatted(self) -> None:
        # black reports "already formatted" by raising rather than by returning
        # the content unchanged. Letting that escape loses the autofix that
        # produced the module, so the formatter has to treat it as a no-op.
        config = Config(path=FAKE_PATH, formatter="black")
        for content, expected in (
            (b"x = 1\n", b"x = 1\n"),
            (b"x=1\n", b"x = 1\n"),
        ):
            with self.subTest(content=content):
                module = libcst.parse_module(content)
                self.assertEqual(expected, format_module(module, FAKE_PATH, config))

    def test_no_formatter_returns_module_bytes(self) -> None:
        config = Config(path=FAKE_PATH)
        module = libcst.parse_module(b"x=1\n")
        self.assertEqual(b"x=1\n", format_module(module, FAKE_PATH, config))
