# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Optional, Set, Union

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
            def isinstance(x, y):
                return None
            if isinstance(x, y) or isinstance(x, z):
                pass
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
            "isinstance(x, y) or isinstance(x, z) or isinstance(x, q) or isinstance(x, w)",
            expected_replacement="isinstance(x, (y, z, q, w))",
        ),
        Invalid(
            "isinstance(x, a) or isinstance(x, b) or isinstance(y, c) or isinstance(y, d)",
            expected_replacement="isinstance(x, (a, b)) or isinstance(y, (c, d))",
        ),
        Invalid(
            "isinstance(x, a) or isinstance(x, b) or isinstance(y, c) or isinstance(y, d) "
            + " or isinstance(z, e)",
            expected_replacement="isinstance(x, (a, b)) or isinstance(y, (c, d)) or isinstance(z, e)",
        ),
        Invalid(
            "isinstance(x, a) or isinstance(x, b) or isinstance(y, c) or isinstance(y, d) "
            + " or isinstance(z, e) or isinstance(q, f) or isinstance(q, g) or isinstance(q, h)",
            expected_replacement=(
                "isinstance(x, (a, b)) or isinstance(y, (c, d)) or isinstance(z, e)"
                + " or isinstance(q, (f, g, h))"
            ),
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
            calls = self._collect_isinstance_calls(node)
            if calls is None:
                return None

            replacement = self._merge_isinstance_calls(calls)
            if replacement is not None:
                self.report(node, replacement=replacement)

    def _collect_isinstance_calls(
        self, node: cst.BooleanOperation
    ) -> Optional[List[cst.Call]]:
        expected_call = m.Call(
            func=m.Name(value="isinstance"),
            args=[
                m.Arg(),
                m.Arg(value=~m.Tuple()),
            ],
        )
        expected_boolop = m.BooleanOperation(operator=m.Or(), right=expected_call)

        seen = []
        stack: List[cst.Call] = []
        current = node
        while m.matches(current, expected_boolop):
            current = cst.ensure_type(current, cst.BooleanOperation)
            seen.append(current)
            stack.insert(0, cst.ensure_type(current.right, cst.Call))
            current = current.left

        if m.matches(current, expected_call):
            stack.insert(0, cst.ensure_type(current, cst.Call))
        else:
            return None

        self.seen_boolean_operations.update(seen)
        return stack

    def _merge_isinstance_calls(
        self, stack: List[cst.Call]
    ) -> Optional[Union[cst.Call, cst.BooleanOperation]]:

        targets = {}
        for call in stack:
            func = cst.ensure_type(call, cst.Call).func
            for context in self.get_metadata(QualifiedNameProvider, func):
                if (
                    context.name != "builtins.isinstance"
                    or context.source is not QualifiedNameSource.BUILTIN
                ):
                    return None

            target, match = call.args[0].value, call.args[1].value
            for possible_target in targets:
                if target.deep_equals(possible_target):
                    targets[possible_target].append(match)
                    break
            else:
                targets[target] = [match]

        if all(len(matches) == 1 for matches in targets.values()):
            return None

        replacement = None
        for target, matches in targets.items():
            if len(matches) == 1:
                arg = cst.Arg(*matches)
            else:
                arg = cst.Arg(cst.Tuple([cst.Element(match) for match in matches]))
            call = cst.Call(cst.Name("isinstance"), [cst.Arg(target), arg])
            if replacement is None:
                replacement = call
            elif isinstance(replacement, (cst.Call, cst.BooleanOperation)):
                replacement = cst.BooleanOperation(
                    left=replacement, right=call, operator=cst.Or()
                )

        return replacement
