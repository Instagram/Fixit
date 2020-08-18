# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class AvoidOrInExceptRule(CstLintRule):
    MESSAGE: str = (
        "Avoid using 'or' in an except block. For example:"
        + "'except ValueError or TypeError' only catches 'ValueError'. Instead, use "
        + "parentheses, 'except (ValueError, TypeError)'"
    )
    VALID = [
        Valid(
            """
            try:
                print()
            except (ValueError, TypeError) as err:
                pass
            """
        )
    ]

    INVALID = [
        Invalid(
            """
            try:
                print()
            except ValueError or TypeError:
                pass
            """,
        )
    ]

    def visit_Try(self, node: cst.Try) -> None:
        if m.matches(
            node,
            m.Try(handlers=[m.ExceptHandler(type=m.BooleanOperation(operator=m.Or()))]),
        ):
            self.report(node)
