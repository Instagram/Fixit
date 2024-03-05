# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Union

import libcst as cst
import libcst.matchers as m

from fixit import Invalid, LintRule, Valid


LineType = Union[cst.BaseSmallStatement, cst.BaseStatement]


class SortedAttributes(LintRule):
    """
    Ever wanted to sort a bunch of class attributes alphabetically?
    Well now it's easy! Just add "@sorted-attributes" in the doc string of
    a class definition and lint will automatically sort all attributes alphabetically.

    Feel free to add other methods and such -- it should only affect class attributes.
    """

    INVALID = [
        Invalid(
            """
            class MyUnsortedConstants:
                \"\"\"
                @sorted-attributes
                \"\"\"
                z = "hehehe"
                B = 'aaa234'
                A = 'zzz123'
                cab = "foo bar"
                Daaa = "banana"

                @classmethod
                def get_foo(cls) -> str:
                    return "some random thing"
           """,
            expected_replacement="""
            class MyUnsortedConstants:
                \"\"\"
                @sorted-attributes
                \"\"\"
                A = 'zzz123'
                B = 'aaa234'
                Daaa = "banana"
                cab = "foo bar"
                z = "hehehe"

                @classmethod
                def get_foo(cls) -> str:
                    return "some random thing"
           """,
        )
    ]
    VALID = [
        Valid(
            """
            class MyConstants:
                \"\"\"
                @sorted-attributes
                \"\"\"
                A = 'zzz123'
                B = 'aaa234'

            class MyUnsortedConstants:
                B = 'aaa234'
                A = 'zzz123'
           """
        )
    ]
    MESSAGE: str = (
        "It appears you are using the @sorted-attributes directive and the class variables are unsorted. See the lint autofix suggestion."
    )

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        doc_string = node.get_docstring()
        if not doc_string or "@sorted-attributes" not in doc_string:
            return

        found_any_assign: bool = False
        pre_assign_lines: List[LineType] = []
        assign_lines: List[LineType] = []
        post_assign_lines: List[LineType] = []

        def _add_unmatched_line(line: LineType) -> None:
            (
                post_assign_lines.append(line)
                if found_any_assign
                else pre_assign_lines.append(line)
            )

        for line in node.body.body:
            if m.matches(
                line, m.SimpleStatementLine(body=[m.Assign(targets=[m.AssignTarget()])])
            ):
                found_any_assign = True
                assign_lines.append(line)
            else:
                _add_unmatched_line(line)
                continue

        sorted_assign_lines = sorted(
            assign_lines, key=lambda line: line.body[0].targets[0].target.value  # type: ignore
        )
        if sorted_assign_lines == assign_lines:
            return
        self.report(
            node,
            replacement=node.with_changes(
                body=node.body.with_changes(
                    body=pre_assign_lines + sorted_assign_lines + post_assign_lines
                )
            ),
        )
