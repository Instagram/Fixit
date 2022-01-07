# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import unittest

from fixit.common.base import _get_code


class GetCodeTest(unittest.TestCase):
    def test_validate_message_old_code(self) -> None:
        # lint-ignore: UseClassNameAsCodeRule
        self.assertEqual(_get_code("IG00 Old-school message", "SomeClassName"), "IG00")

    def test_return_classname(self) -> None:
        self.assertEqual(
            _get_code("Message blah blah", "SomeClassName"), "SomeClassName"
        )
