# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m
from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


IG142_UNNECESSARY_GENERATOR: str = (
    "IG142 It's unnecessary to use {func} around a geneartor expression, since "
    + "there are equivalent comprehensions for this type."
)
IG143_UNNECESSARY_LIST_COMPREHENSION: str = (
    "IG143 It's unnecessary to use a list comprehension inside a call to {func} "
    + "since there are equivalent comprehensions for this type"
)


class RewriteToComprehension(CstLintRule):
    """
    A derivative of flake8-comprehensions's C400-C402 and C403-C404.
    Comprehensions are more efficient than functions calls. This C400-C402
    suggest to use `dict/set/list` comprehensions rather than respective
    function calls whenever possible. C403-C404 suggest to remove unnecessary
    list comprehension in a set/dict call, and replace it with set/dict
    comprehension.
    """

    VALID = [
        Valid("[val for val in iterable]"),
        Valid("{val for val in iterable}"),
        Valid("{val: val+1 for val in iterable}"),
        # A function call is valid if the elt is a function that returns a tuple.
        Valid("dict(line.strip().split('=', 1) for line in attr_file)"),
    ]

    INVALID = [
        # IG142
        Invalid(
            "list(val for val in iterable)",
            "IG142",
            expected_replacement="[val for val in iterable]",
        ),
        # Nested list comprehenstion
        Invalid(
            "list(val for row in matrix for val in row)",
            "IG142",
            expected_replacement="[val for row in matrix for val in row]",
        ),
        Invalid(
            "set(val for val in iterable)",
            "IG142",
            expected_replacement="{val for val in iterable}",
        ),
        Invalid(
            "dict((x, f(x)) for val in iterable)",
            "IG142",
            expected_replacement="{x: f(x) for val in iterable}",
        ),
        Invalid(
            "dict((x, y) for y, x in iterable)",
            "IG142",
            expected_replacement="{x: y for y, x in iterable}",
        ),
        Invalid(
            "dict([val, val+1] for val in iterable)",
            "IG142",
            expected_replacement="{val: val+1 for val in iterable}",
        ),
        Invalid(
            'dict((x["name"], json.loads(x["data"])) for x in responses)',
            "IG142",
            expected_replacement='{x["name"]: json.loads(x["data"]) for x in responses}',
        ),
        # Nested dict comprehension
        Invalid(
            "dict((k, v) for k, v in iter for iter in iters)",
            "IG142",
            expected_replacement="{k: v for k, v in iter for iter in iters}",
        ),
        # IG143
        Invalid(
            "set([val for val in iterable])",
            "IG143",
            expected_replacement="{val for val in iterable}",
        ),
        Invalid(
            "dict([[val, val+1] for val in iterable])",
            "IG143",
            expected_replacement="{val: val+1 for val in iterable}",
        ),
        Invalid(
            "dict([(x, f(x)) for x in foo])",
            "IG143",
            expected_replacement="{x: f(x) for x in foo}",
        ),
        Invalid(
            "dict([(x, y) for y, x in iterable])",
            "IG143",
            expected_replacement="{x: y for y, x in iterable}",
        ),
        Invalid(
            "set([val for row in matrix for val in row])",
            "IG143",
            expected_replacement="{val for row in matrix for val in row}",
        ),
    ]

    def visit_Call(self, node: cst.Call) -> None:
        if m.matches(
            node,
            m.Call(
                func=m.Name("list") | m.Name("set") | m.Name("dict"),
                args=[m.Arg(value=m.GeneratorExp() | m.ListComp())],
            ),
        ):
            call_name = cst.ensure_type(node.func, cst.Name).value

            if m.matches(node.args[0].value, m.GeneratorExp()):
                exp = cst.ensure_type(node.args[0].value, cst.GeneratorExp)
                message_formatter = IG142_UNNECESSARY_GENERATOR
            else:
                exp = cst.ensure_type(node.args[0].value, cst.ListComp)
                message_formatter = IG143_UNNECESSARY_LIST_COMPREHENSION

            replacement = None
            if call_name == "list":
                replacement = node.deep_replace(
                    node, cst.ListComp(elt=exp.elt, for_in=exp.for_in)
                )
            elif call_name == "set":
                replacement = node.deep_replace(
                    node, cst.SetComp(elt=exp.elt, for_in=exp.for_in)
                )
            elif call_name == "dict":
                elt = exp.elt
                key = None
                value = None
                if m.matches(elt, m.Tuple(m.DoNotCare(), m.DoNotCare())):
                    elt = cst.ensure_type(elt, cst.Tuple)
                    key = elt.elements[0].value
                    value = elt.elements[1].value
                elif m.matches(elt, m.List(m.DoNotCare(), m.DoNotCare())):
                    elt = cst.ensure_type(elt, cst.List)
                    key = elt.elements[0].value
                    value = elt.elements[1].value
                else:
                    # Unrecoginized form
                    return

                replacement = node.deep_replace(
                    node,
                    # pyre-fixme[6]: Expected `BaseAssignTargetExpression` for 1st
                    #  param but got `BaseExpression`.
                    cst.DictComp(key=key, value=value, for_in=exp.for_in),
                )

            self.report(
                node, message_formatter.format(func=call_name), replacement=replacement
            )
