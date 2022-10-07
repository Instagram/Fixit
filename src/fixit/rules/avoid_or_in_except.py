# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class AvoidOrInExceptRule(CstLintRule):
    """
    Discourages use of ``or`` in except clauses. If an except clause needs to catch multiple exceptions,
    they must be expressed as a parenthesized tuple, for example:
    ``except (ValueError, TypeError)``
    (https://docs.python.org/3/tutorial/errors.html#handling-exceptions)

    When ``or`` is used, only the first operand exception type of the conditional statement will be caught.
    For example::

        In [1]: class Exc1(Exception):
            ...:     pass
            ...:

        In [2]: class Exc2(Exception):
            ...:     pass
            ...:

        In [3]: try:
            ...:     raise Exception()
            ...: except Exc1 or Exc2:
            ...:     print("caught!")
            ...:
        ---------------------------------------------------------------------------
        Exception                                 Traceback (most recent call last)
        <ipython-input-3-3340d66a006c> in <module>
            1 try:
        ----> 2     raise Exception()
            3 except Exc1 or Exc2:
            4     print("caught!")
            5

        Exception:

        In [4]: try:
            ...:     raise Exc1()
            ...: except Exc1 or Exc2:
            ...:     print("caught!")
            ...:
            caught!

        In [5]: try:
            ...:     raise Exc2()
            ...: except Exc1 or Exc2:
            ...:     print("caught!")
            ...:
        ---------------------------------------------------------------------------
        Exc2                                      Traceback (most recent call last)
        <ipython-input-5-5d29c1589cc0> in <module>
            1 try:
        ----> 2     raise Exc2()
            3 except Exc1 or Exc2:
            4     print("caught!")
            5

        Exc2:
    """

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
