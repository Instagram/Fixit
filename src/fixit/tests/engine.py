# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path
from textwrap import dedent
from unittest import TestCase

from libcst import (
    Call,
    ensure_type,
    Expr,
    parse_module,
    SimpleStatementLine,
    SimpleString,
)
from libcst.metadata import CodePosition, CodeRange

from ..engine import diff_violation
from ..ftypes import LintViolation


class EngineTest(TestCase):
    def test_diff_violation(self) -> None:
        src = dedent(
            """\
                import sys
                print("hello world")
            """
        )
        path = Path("foo.py")
        module = parse_module(src)
        node = ensure_type(
            ensure_type(
                ensure_type(module.body[-1], SimpleStatementLine).body[0], Expr
            ).value,
            Call,
        ).args[0]
        repl = node.with_changes(value=SimpleString('"goodnight moon"'))

        violation = LintViolation(
            "Fake",
            CodeRange(CodePosition(1, 1), CodePosition(2, 2)),
            message="some error",
            node=node,
            replacement=repl,
        )

        expected = dedent(
            """\
                --- a/foo.py
                +++ b/foo.py
                @@ -1,2 +1,2 @@
                 import sys
                -print("hello world")
                +print("goodnight moon")
            """
        )
        result = diff_violation(path, module, violation)
        self.assertEqual(expected, result)
