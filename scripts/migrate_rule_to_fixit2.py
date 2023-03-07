#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import functools
import sys
from argparse import ArgumentParser
from typing import Collection, Optional

from libcst import Arg, BaseExpression, Call, matchers as m, Name, parse_expression
from libcst.codemod import (
    CodemodContext,
    parallel_exec_transform_with_prettyprint,
    VisitorBasedCodemodCommand,
)
from libcst.codemod.visitors import AddImportsVisitor
from libcst.metadata import QualifiedName, QualifiedNameProvider


def _match(name, metadata: Collection[QualifiedName]) -> bool:
    for item in metadata:
        if item.name == name:
            return True
    return False


def match_qualified_name(name: str):
    return m.MatchMetadataIfTrue(QualifiedNameProvider, functools.partial(_match, name))


class MigrateRuleToFixit2(VisitorBasedCodemodCommand):
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    @m.call_if_inside(
        m.SimpleStatementLine(
            body=[m.Assign(targets=[m.AssignTarget(target=m.Name(value="INVALID"))])]
        )
    )
    @m.leave(
        m.Call(
            func=match_qualified_name("fixit.InvalidTestCase"),
        )
    )
    def convert_linecol_to_range(self, original_node: Call, updated_node: Call) -> Call:
        line: Optional[BaseExpression] = None
        col: Optional[BaseExpression] = None
        index_to_remove = []
        for ind, arg in enumerate(updated_node.args):
            if m.matches(arg.keyword, m.Name("line")):
                line = arg.value
                index_to_remove.append(ind)
            elif m.matches(arg.keyword, m.Name("column")):
                col = arg.value
                index_to_remove.append(ind)

        if line:
            args = list(updated_node.args[:])
            for ind in reversed(sorted(index_to_remove)):
                args.pop(ind)

            line_str = self.context.module.code_for_node(line)
            col_str = self.context.module.code_for_node(col) if col else "0"
            coderange_expr = parse_expression(
                f"CodeRange(start=CodePosition({line_str}, {col_str}), end=CodePosition(1 + {line_str}, 0))",
                self.context.module.config_for_parsing,
            )
            args.append(Arg(keyword=Name("range"), value=coderange_expr))
            for cls in ("CodeRange", "CodePosition"):
                AddImportsVisitor.add_needed_import(self.context, "fixit", cls)
            return updated_node.with_changes(args=args)
        return updated_node


def main() -> None:
    parser = ArgumentParser(description="Convert fixit1 rule to fixit2")
    parser.add_argument(
        "filename", nargs="+", help="File name containing rule implementation"
    )
    args = parser.parse_args()
    result = parallel_exec_transform_with_prettyprint(
        MigrateRuleToFixit2(CodemodContext()),
        args.filename,
        repo_root=".",
        jobs=1,
    )
    print(f"Transformed {result.successes} files successfully.")
    print(f"Skipped {result.skips} files.")
    print(f"Failed to codemod {result.failures} files.")
    print(f"{result.warnings} warnings were generated.")
    sys.exit(1 if result.failures else 0)


if __name__ == "__main__":
    main()
