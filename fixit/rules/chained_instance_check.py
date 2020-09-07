# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Dict, Iterator, List, Set, Tuple

import libcst as cst
import libcst.matchers as m
from libcst.metadata import QualifiedName, QualifiedNameProvider, QualifiedNameSource

from fixit import (
    CstContext,
    CstLintRule,
    InvalidTestCase as Invalid,
    ValidTestCase as Valid,
)


_ISINSTANCE = QualifiedName(
    name="builtins.isinstance", source=QualifiedNameSource.BUILTIN
)


class CollapseIsinstanceChecksRule(CstLintRule):
    """
    The built-in ``isinstance`` function, instead of a single type,
    can take a tuple of types and check whether given target suits
    any of them. Rather than chaining multiple ``isinstance`` calls
    with a boolean-or operation, a single ``isinstance`` call where
    the second argument is a tuple of all types can be used.
    """

    MESSAGE: str = (
        "Multiple isinstance calls with the same target but "
        + "different types can be collapsed into a single call "
        + "with a tuple of types."
    )

    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    VALID = [
        Valid("foo() or foo()"),
        Valid("foo(x, y) or foo(x, z)"),
        Valid("foo(x, y) or foo(x, z) or foo(x, q)"),
        Valid("isinstance() or isinstance()"),
        Valid("isinstance(x) or isinstance(x)"),
        Valid("isinstance(x, y) or isinstance(x)"),
        Valid("isinstance(x) or isinstance(x, y)"),
        Valid("isinstance(x, y) or isinstance(t, y)"),
        Valid("isinstance(x, y) and isinstance(x, z)"),
        Valid("isinstance(x, y) or isinstance(x, (z, q))"),
        Valid("isinstance(x, (y, z)) or isinstance(x, q)"),
        Valid("isinstance(x, a) or isinstance(y, b) or isinstance(z, c)"),
        Valid(
            """
            def foo():
                def isinstance(x, y):
                    return _foo_bar(x, y)
                if isinstance(x, y) or isinstance(x, z):
                    print("foo")
            """
        ),
    ]
    INVALID = [
        Invalid(
            "isinstance(x, y) or isinstance(x, z)",
            expected_replacement="isinstance(x, (y, z))",
        ),
        Invalid(
            "isinstance(x, y) or isinstance(x, z) or isinstance(x, q)",
            expected_replacement="isinstance(x, (y, z, q))",
        ),
        Invalid(
            "something or isinstance(x, y) or isinstance(x, z) or another",
            expected_replacement="something or isinstance(x, (y, z)) or another"
        ),
        Invalid(
            "isinstance(x, y) or isinstance(x, z) or isinstance(x, q) or isinstance(x, w)",
            expected_replacement="isinstance(x, (y, z, q, w))",
        ),
        Invalid(
            "isinstance(x, a) or isinstance(x, b) or isinstance(y, c) or isinstance(y, d)",
            expected_replacement="isinstance(x, (a, b)) or isinstance(y, (c, d))",
        ),
        Invalid(
            "isinstance(x, a) or isinstance(x, b) or isinstance(y, c) or isinstance(y, d) "
            + "or isinstance(z, e)",
            expected_replacement="isinstance(x, (a, b)) or isinstance(y, (c, d)) or isinstance(z, e)",
        ),
        Invalid(
            "isinstance(x, a) or isinstance(x, b) or isinstance(y, c) or isinstance(y, d) "
            + "or isinstance(z, e) or isinstance(q, f) or isinstance(q, g) or isinstance(q, h)",
            expected_replacement=(
                "isinstance(x, (a, b)) or isinstance(y, (c, d)) or isinstance(z, e)"
                + " or isinstance(q, (f, g, h))"
            ),
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        self.seen_boolean_operations: Set[cst.BooleanOperation] = set()

    def visit_BooleanOperation(self, node: cst.BooleanOperation) -> None:
        if node in self.seen_boolean_operations:
            return None

        stack = tuple(self.unwrap(node))
        operands, targets = self.collect_targets(stack)

        # If nothing gets collapsed, just exit from this short-path
        if len(operands) == len(stack):
            return None

        replacement = None
        for operand in operands:
            if operand in targets:
                matches = targets[operand]
                if len(matches) == 1:
                    arg = cst.Arg(value=matches[0])
                else:
                    arg = cst.Arg(cst.Tuple([cst.Element(match) for match in matches]))
                operand = cst.Call(cst.Name("isinstance"), [cst.Arg(operand), arg])

            if replacement is None:
                replacement = operand
            else:
                replacement = cst.BooleanOperation(
                    left=replacement, right=operand, operator=cst.Or()
                )

        if replacement is not None:
            self.report(node, replacement=replacement)

    def unwrap(self, node: cst.BaseExpression) -> Iterator[cst.BaseExpression]:
        if m.matches(node, m.BooleanOperation(operator=m.Or())):
            bool_op = cst.ensure_type(node, cst.BooleanOperation)
            self.seen_boolean_operations.add(bool_op)
            yield from self.unwrap(bool_op.left)
            yield bool_op.right
        else:
            yield node

    def collect_targets(
        self, stack: Tuple[cst.BaseExpression, ...]
    ) -> Tuple[
        List[cst.BaseExpression], Dict[cst.BaseExpression, List[cst.BaseExpression]]
    ]:
        targets = {}
        operands = []

        for operand in stack:
            if m.matches(
                operand, m.Call(func=m.DoNotCare(), args=[m.Arg(), m.Arg(~m.Tuple())])
            ):
                call = cst.ensure_type(operand, cst.Call)
                if not QualifiedNameProvider.has_name(self, call, _ISINSTANCE):
                    operands.append(operand)
                    continue

                target, match = call.args[0].value, call.args[1].value
                for possible_target in targets:
                    if target.deep_equals(possible_target):
                        targets[possible_target].append(match)
                        break
                else:
                    operands.append(target)
                    targets[target] = [match]
            else:
                operands.append(operand)

        return operands, targets
