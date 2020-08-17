# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
import libcst.matchers as m

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


IG66_UNNECESSARY_LIST_COMPREHENSION: str = (
    "Unnecessary list comprehension - {func} can take a generator, and is likely "
    + "to short-circuit, so constructing a list is probably wasteful."
)


class UnnecessaryListComprehensionRule(CstLintRule):
    """
    A derivative of flake8-comprehensions's C407 rule.
    """

    VALID = [
        Valid("any(val for val in iterable)"),
        Valid("all(val for val in iterable)"),
        # C407 would complain about these, but we won't
        Valid("frozenset([val for val in iterable])"),
        Valid("max([val for val in iterable])"),
        Valid("min([val for val in iterable])"),
        Valid("sorted([val for val in iterable])"),
        Valid("sum([val for val in iterable])"),
        Valid("tuple([val for val in iterable])"),
    ]
    INVALID = [
        Invalid(
            "any([val for val in iterable])",
            "UnnecessaryListComprehensionRule",
            expected_replacement="any(val for val in iterable)",
        ),
        Invalid(
            "all([val for val in iterable])",
            "UnnecessaryListComprehensionRule",
            expected_replacement="all(val for val in iterable)",
        ),
    ]

    def visit_Call(self, node: cst.Call) -> None:
        # This set excludes frozenset, max, min, sorted, sum, and tuple, which C407 would warn
        # about, because none of those functions short-circuit.
        if m.matches(
            node,
            m.Call(
                func=m.Name("all") | m.Name("any"), args=[m.Arg(value=m.ListComp())]
            ),
        ):
            list_comp = cst.ensure_type(node.args[0].value, cst.ListComp)
            self.report(
                node,
                IG66_UNNECESSARY_LIST_COMPREHENSION.format(
                    func=cst.ensure_type(node.func, cst.Name).value
                ),
                replacement=node.deep_replace(
                    list_comp,
                    cst.GeneratorExp(
                        elt=list_comp.elt, for_in=list_comp.for_in, lpar=[], rpar=[]
                    ),
                ),
            )
