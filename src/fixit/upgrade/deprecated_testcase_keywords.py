#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Optional

from libcst import (
    Arg,
    BaseExpression,
    Call,
    matchers as m,
    Module,
    Name,
    parse_expression,
)
from libcst.metadata import QualifiedNameProvider

from fixit import Invalid, LintRule, Valid


class FixitDeprecatedTestCaseKeywords(LintRule):
    """
    Modify lint rule test cases from Fixit 1 to remove deprecated keyword arguments
    and convert the line and column values into a CodeRange.

    .. important::
       The use of ``fixit.ValidTestCase`` and ``fixit.InvalidTestCase`` have been
       deprecated. This rule provides upgrades only to the temporary aliases.

       Use ``fixit upgrade`` to replace the aliases with :class:`fixit.Valid` and
       :class:`fixit.Invalid`.

       See the :ref:`Version 2 API Changes <v2-api-changes>` for more details.
    """

    MESSAGE = "Fix deprecated ValidTestCase/InvalidTestCase keyword arguments"
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    VALID = [
        Valid(
            """
            from fixit import InvalidTestCase

            InvalidTestCase(
                "print('hello')",
                message="oops",
            )
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            from fixit import InvalidTestCase

            InvalidTestCase(
                "print('hello')",
                line=3,
                column=10,
                config=None,
                filename="hello.py",
                kind="X123",
            )
            """,
            expected_replacement="""
            from fixit import InvalidTestCase

            InvalidTestCase(
                "print('hello')",
                range = CodeRange(start=CodePosition(3, 10), end=CodePosition(1 + 3, 0)))
            """,
        ),
    ]

    def visit_Module(self, module: Module) -> None:
        self.module = module

    def visit_Call(self, node: Call) -> None:
        metadata = self.get_metadata(QualifiedNameProvider, node)
        for item in metadata:
            if item.name in ("fixit.InvalidTestCase", "fixit.ValidTestCase"):
                self.convert_linecol_to_range(node)

    def convert_linecol_to_range(self, node: Call) -> None:
        line: Optional[BaseExpression] = None
        col: Optional[BaseExpression] = None
        index_to_remove = []
        for ind, arg in enumerate(node.args):
            if not arg.keyword:
                continue
            if m.matches(arg.keyword, m.Name("line")):
                line = arg.value
                index_to_remove.append(ind)
            elif m.matches(arg.keyword, m.Name("column")):
                col = arg.value
                index_to_remove.append(ind)
            elif m.matches(
                arg.keyword,
                m.OneOf(*(m.Name(k) for k in ("config", "filename", "kind"))),
            ):
                index_to_remove.append(ind)

        args = list(node.args[:])
        for ind in reversed(sorted(index_to_remove)):
            args.pop(ind)

        if line:
            line_str = self.module.code_for_node(line)
            col_str = self.module.code_for_node(col) if col else "0"
            coderange_expr = parse_expression(
                f"CodeRange(start=CodePosition({line_str}, {col_str}), end=CodePosition(1 + {line_str}, 0))",
                self.module.config_for_parsing,
            )
            args.append(Arg(keyword=Name("range"), value=coderange_expr))

        if index_to_remove:
            self.report(node, replacement=node.with_changes(args=args))
