# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Sequence

import libcst as cst
import libcst.matchers as m

from fixit import Invalid, LintRule, Valid


UNNECESSARY_LITERAL: str = (
    "It's unnecessary to use a list or tuple within a call to {func} since"
    + " there is literal syntax for this type"
)
UNNCESSARY_CALL: str = (
    "It's slower to call {func}() than using the empty literal, because"
    + " the name {func} must be looked up in the global scope in case it has"
    + " been rebound."
)


class RewriteToLiteralRule(LintRule):
    """
    A derivative of flake8-comprehensions' C405-C406 and C409-C410. It's
    unnecessary to use a list or tuple literal within a call to tuple, list,
    set, or dict since there is literal syntax for these types.
    """

    VALID = [
        Valid("(1, 2)"),
        Valid("()"),
        Valid("[1, 2]"),
        Valid("[]"),
        Valid("{1, 2}"),
        Valid("set()"),
        Valid("{1: 2, 3: 4}"),
        Valid("{}"),
    ]

    INVALID = [
        Invalid("tuple([1, 2])", expected_replacement="(1, 2)"),
        Invalid("tuple((1, 2))", expected_replacement="(1, 2)"),
        Invalid("tuple([])", expected_replacement="()"),
        Invalid("list([1, 2, 3])", expected_replacement="[1, 2, 3]"),
        Invalid("list((1, 2, 3))", expected_replacement="[1, 2, 3]"),
        Invalid("list([])", expected_replacement="[]"),
        Invalid("set([1, 2, 3])", expected_replacement="{1, 2, 3}"),
        Invalid("set((1, 2, 3))", expected_replacement="{1, 2, 3}"),
        Invalid("set([])", expected_replacement="set()"),
        Invalid(
            "dict([(1, 2), (3, 4)])",
            expected_replacement="{1: 2, 3: 4}",
        ),
        Invalid(
            "dict(((1, 2), (3, 4)))",
            expected_replacement="{1: 2, 3: 4}",
        ),
        Invalid(
            "dict([[1, 2], [3, 4], [5, 6]])",
            expected_replacement="{1: 2, 3: 4, 5: 6}",
        ),
        Invalid("dict([])", expected_replacement="{}"),
        Invalid("tuple()", expected_replacement="()"),
        Invalid("list()", expected_replacement="[]"),
        Invalid("dict()", expected_replacement="{}"),
    ]

    def visit_Call(self, node: cst.Call) -> None:
        if m.matches(
            node,
            m.Call(
                func=m.Name("tuple") | m.Name("list") | m.Name("set") | m.Name("dict"),
                args=[m.Arg(value=m.List() | m.Tuple())],
            ),
        ) or m.matches(
            node,
            m.Call(func=m.Name("tuple") | m.Name("list") | m.Name("dict"), args=[]),
        ):
            pairs_matcher = m.ZeroOrMore(
                m.Element(m.Tuple(elements=[m.DoNotCare(), m.DoNotCare()]))
                | m.Element(m.List(elements=[m.DoNotCare(), m.DoNotCare()]))
            )

            exp = cst.ensure_type(node, cst.Call)
            call_name = cst.ensure_type(exp.func, cst.Name).value

            # If this is a empty call, it's an Unnecessary Call where we rewrite the call
            # to literal, except set().
            elements: Sequence[cst.BaseElement]
            if not exp.args:
                elements = []
                message_formatter = UNNCESSARY_CALL
            else:
                arg = exp.args[0].value
                if isinstance(arg, cst.List):
                    elements = arg.elements
                elif isinstance(arg, cst.Tuple):
                    elements = arg.elements
                else:
                    raise ValueError(f"Unexpected {type(arg)}")
                message_formatter = UNNECESSARY_LITERAL

            new_node: cst.CSTNode
            if call_name == "tuple":
                new_node = cst.Tuple(elements=elements)
            elif call_name == "list":
                new_node = cst.List(elements=elements)
            elif call_name == "set":
                # set() doesn't have an equivelant literal call. If it was
                # matched here, it's an unnecessary literal suggestion.
                if len(elements) == 0:
                    self.report(
                        node,
                        UNNECESSARY_LITERAL.format(func=call_name),
                        replacement=node.deep_replace(
                            node, cst.Call(func=cst.Name("set"))
                        ),
                    )
                    return
                new_node = cst.Set(elements=elements)
            elif len(elements) == 0 or m.matches(
                exp.args[0].value,
                m.Tuple(elements=[pairs_matcher]) | m.List(elements=[pairs_matcher]),
            ):
                new_node = cst.Dict(
                    elements=[
                        (
                            lambda val: cst.DictElement(
                                val.elements[0].value, val.elements[1].value  # type: ignore
                            )
                        )(
                            cst.ensure_type(
                                ele.value,
                                cst.Tuple  # type: ignore
                                if isinstance(ele.value, cst.Tuple)
                                else cst.List,
                            )
                        )
                        for ele in elements
                    ]
                )
            else:
                # Unrecoginized form
                return

            self.report(
                node,
                message_formatter.format(func=call_name),
                replacement=node.deep_replace(node, new_node),
            )
