# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Optional, Set

import libcst as cst
import libcst.matchers as m

from fixit import (
    CstContext,
    CstLintRule,
    InvalidTestCase as Invalid,
    ValidTestCase as Valid,
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
            "isinstance(x, y) or isinstance(x, z) or isinstance(x, q) or isinstance(x, w)",
            expected_replacement="isinstance(x, (y, z, q, w))",
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)

        # Since we already unwrap a boolean op's
        # children
        self.seen_boolean_operations: Set[cst.BooleanOperation] = set()

    def visit_BooleanOperation(self, node: cst.BooleanOperation) -> None:
        # Initially match with a partial pattern (in order to ensure
        # we have enough args to construct more accurate / advanced
        # pattern).
        if node not in self.seen_boolean_operations and m.matches(
            node,
            m.BooleanOperation(right=m.Call(args=[m.AtLeastN(n=1)]), operator=m.Or()),
        ):
            args = self._collect_isinstance_args(node)
            if args is not None:
                right = cst.ensure_type(node.right, cst.Call)
                elements = [cst.Element(arg.value) for arg in args]
                new_isinstance_call = right.with_deep_changes(
                    old_node=right.args[1], value=cst.Tuple(elements)
                )
                self.report(node, replacement=new_isinstance_call)

    def _collect_isinstance_args(
        self, node: cst.BooleanOperation
    ) -> Optional[List[cst.Arg]]:
        target = cst.ensure_type(node.right, cst.Call).args[0].value
        expected_call = m.Call(
            func=m.Name(value="isinstance"),
            args=[
                m.Arg(value=m.MatchIfTrue(target.deep_equals)),
                m.Arg(value=~m.Tuple()),
            ],
        )
        expected_boolop = m.BooleanOperation(operator=m.Or(), right=expected_call)

        seen = []
        stack = []
        current = node
        while m.matches(current, expected_boolop):
            current = cst.ensure_type(current, cst.BooleanOperation)
            seen.append(current)
            stack.insert(0, current.right)
            current = current.left

        if m.matches(current, expected_call):
            stack.insert(0, current)
            self.seen_boolean_operations.update(seen)
        else:
            return None

        return [cst.ensure_type(node, cst.Call).args[1] for node in stack]
