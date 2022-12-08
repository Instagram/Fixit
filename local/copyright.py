# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from textwrap import dedent

import libcst as cst
from fixit import CSTLintRule


class FixitCopyrightRule(CSTLintRule):
    """
    Simple rule to enforce the Meta copyright header
    """

    DESIRED_HEADER = """
        # Copyright (c) Meta Platforms, Inc. and affiliates.
        #
        # This source code is licensed under the MIT license found in the
        # LICENSE file in the root directory of this source tree.
    """

    def visit_Module(self, node: cst.Module) -> None:
        header_lines = [
            (eline.whitespace.value + (eline.comment.value if eline.comment else ""))
            for eline in node.header
        ]

        shebang = ""
        if header_lines[0].startswith("#!"):
            shebang = header_lines[0]
            header_lines = header_lines[1:]

        header_str = "\n".join(header_lines)
        desired = dedent(self.DESIRED_HEADER).strip()

        if desired not in header_str:
            header_str = desired + "\n\n" + header_str

            new_header = []
            if shebang:
                new_header.append(
                    cst.EmptyLine(
                        whitespace=cst.SimpleWhitespace(""),
                        comment=cst.Comment(shebang),
                    )
                )

            for line in header_str.splitlines():
                ws, _, comment = line.partition("#")
                if comment:
                    comment = "#" + comment
                    new_header.append(
                        cst.EmptyLine(
                            whitespace=cst.SimpleWhitespace(ws),
                            comment=cst.Comment(comment),
                        )
                    )
                else:
                    new_header.append(
                        cst.EmptyLine(whitespace=cst.SimpleWhitespace(ws))
                    )

            replacement = node.with_changes(header=new_header)
            self.report(node, "Copyright header not found", replacement=replacement)
