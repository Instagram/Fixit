# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import FrozenSet, Union

import libcst as cst
from libcst.metadata import QualifiedName, QualifiedNameProvider, QualifiedNameSource

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class CompareSingletonPrimitivesByIsRule(CstLintRule):
    """
    Enforces the use of `is` and `is not` in comparisons to singleton primitives (None, True, False) rather than == and !=.
    The == operator checks equality, when in this scenario, we want to check identity.
    See Flake8 rules E711 (https://www.flake8rules.com/rules/E711.html) and E712 (https://www.flake8rules.com/rules/E712.html).
    """

    MESSAGE: str = (
        "Comparisons to singleton primitives should not be done with == or !=, as they check equality rather than identiy."
        + " Use `is` or `is not` instead."
    )
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)
    VALID = [
        Valid("if x: pass"),
        Valid("if not x: pass"),
        Valid("x is True"),
        Valid("x is False"),
        Valid("x is None"),
        Valid("x is not None"),
        Valid("x is True is not y"),
        Valid("y is None is not x"),
        Valid("None is y"),
        Valid("True is x"),
        Valid("False is x"),
        Valid("x == 2"),
        Valid("2 != x"),
    ]
    INVALID = [
        Invalid(
            code="x != True",
            expected_replacement="x is not True",
        ),
        Invalid(
            code="x != False",
            expected_replacement="x is not False",
        ),
        Invalid(
            code="x == False",
            expected_replacement="x is False",
        ),
        Invalid(
            code="x == None",
            expected_replacement="x is None",
        ),
        Invalid(
            code="x != None",
            expected_replacement="x is not None",
        ),
        Invalid(
            code="False == x",
            expected_replacement="False is x",
        ),
        Invalid(
            code="x is True == y",
            expected_replacement="x is True is y",
        ),
    ]

    QUALIFIED_SINGLETON_PRIMITIVES: FrozenSet[QualifiedName] = frozenset(
        {
            QualifiedName(name=f"builtins.{name}", source=QualifiedNameSource.BUILTIN)
            for name in ("True", "False", "None")
        }
    )

    def visit_Comparison(self, node: cst.Comparison) -> None:
        # Initialize the needs_report flag as False to begin with
        needs_report = False
        left_comp = node.left
        altered_comparisons = []
        for target in node.comparisons:
            operator, right_comp = target.operator, target.comparator
            if isinstance(operator, (cst.Equal, cst.NotEqual)) and (
                not self.QUALIFIED_SINGLETON_PRIMITIVES.isdisjoint(
                    self.get_metadata(QualifiedNameProvider, left_comp, set())
                )
                or not self.QUALIFIED_SINGLETON_PRIMITIVES.isdisjoint(
                    self.get_metadata(QualifiedNameProvider, right_comp, set())
                )
            ):
                needs_report = True
                altered_comparisons.append(
                    target.with_changes(operator=self.alter_operator(operator))
                )
            else:
                altered_comparisons.append(target)
            # Continue the check down the line of comparisons, if more than one
            left_comp = right_comp

        if needs_report:
            self.report(
                node, replacement=node.with_changes(comparisons=altered_comparisons)
            )

    def alter_operator(
        self, original_op: Union[cst.Equal, cst.NotEqual]
    ) -> Union[cst.Is, cst.IsNot]:
        return (
            cst.IsNot(
                whitespace_before=original_op.whitespace_before,
                whitespace_after=original_op.whitespace_after,
            )
            if isinstance(original_op, cst.NotEqual)
            else cst.Is(
                whitespace_before=original_op.whitespace_before,
                whitespace_after=original_op.whitespace_after,
            )
        )
