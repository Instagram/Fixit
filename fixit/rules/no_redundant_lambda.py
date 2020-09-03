# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m
from libcst.helpers import get_full_name_for_node

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


UNNECESSARY_LAMBDA: str = (
    "The lambda that is wrapping {function} is redundant. "
    + "It can unwrapped safely and used purely."
)


class NoRedundantLambdaFunction(CstLintRule):

    VALID = [
        Valid("lambda x: foo(y)"),
        Valid("lambda x: foo(x, y)"),
        Valid("lambda x, y: foo(x)"),
        Valid("lambda x, /: foo(x)"),
        Valid("lambda *, x: foo(x)"),
        Valid("lambda x = y: foo(x)"),
        Valid("lambda x, y: foo(y, x)"),
        Valid("lambda x, y: foo(y=x, x=y)"),
        Valid("lambda x, y, *z: foo(x, y, z)"),
        Valid("lambda x, y, **z: foo(x, y, z)"),
    ]
    INVALID = [
        Invalid("lambda x: foo(x)", expected_replacement="foo"),
        Invalid(
            "lambda x, y, z: (t + u).math_call(x, y, z)",
            expected_replacement="(t + u).math_call",
        ),
    ]

    @staticmethod
    def _is_simple_parameter_spec(node: cst.Parameters) -> bool:
        if (
            node.star_kwarg is not None
            or len(node.kwonly_params) > 0
            or len(node.posonly_params) > 0
            or not isinstance(node.star_arg, cst.MaybeSentinel)
        ):
            return False

        return all(param.default is None for param in node.params)

    def visit_Lambda(self, node: cst.Lambda) -> None:
        if m.matches(
            node,
            m.Lambda(
                params=m.MatchIfTrue(self._is_simple_parameter_spec),
                body=m.Call(
                    args=[
                        m.Arg(
                            value=m.Name(value=param.name.value), star="", keyword=None
                        )
                        for param in node.params.params
                    ]
                ),
            ),
        ):
            call = cst.ensure_type(node.body, cst.Call)
            full_name = get_full_name_for_node(call)
            if full_name is None:
                full_name = "function"

            self.report(
                node,
                UNNECESSARY_LAMBDA.format(function=full_name),
                replacement=call.func,
            )
