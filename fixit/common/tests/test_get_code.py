# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from libcst.testing.utils import UnitTest

from fixit.common.base import _get_code


class GetCodeTest(UnitTest):
    def test_validate_message(self) -> None:
        self.assertEqual(_get_code("IG00 Message"), "IG00")
        with self.assertRaisesRegex(ValueError, "IGXX"):
            _get_code("Message")
        with self.assertRaisesRegex(ValueError, "space"):
            _get_code("IG00: Message")
