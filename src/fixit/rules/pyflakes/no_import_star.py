# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class NoImportStarRule(CstLintRule):
    """
    Discourage `from ... import *` statements.

    Autofix: N/A
    """

    MESSAGE = ("`from ... import *` is discouraged because it makes it "
        "difficult to see where the imported object is defined. Instead,"
        " explicitly import the desired module, class, or function.")

    def __init__(self) -> None:
        super().__init__()

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if isinstance(node.names, cst.ImportStar):
            self.report(node)

    VALID = [
        Valid(
            """
            from a import b, c, d
            """
        ),
    ]

    INVALID = [
        Invalid(
            """
            from a import *
            """
        ),
    ]
