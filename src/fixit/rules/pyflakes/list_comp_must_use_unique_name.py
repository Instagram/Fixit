# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Optional, Set

import libcst as cst

from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


class ListCompMustUseUniqueNameRule(CstLintRule):
    """
    A list comprehension shouldn't use the same name as another variable
    defined in the module.

    Autofix: N/A
    """

    CUSTOM_MESSAGE = ("The name {name} is already defined in the module."
                      "Although list comprehensions have their own "
                      "scope, it is best practice to use a unique name.")

    METADATA_DEPENDENCIES = (cst.metadata.ScopeProvider,)

    def __init__(self) -> None:
        super().__init__()

    def visit_ListComp(self, node: cst.ListComp) -> None:
        names: Set[str] = set()
        for_in: Optional[cst.CompFor] = node.for_in
        while for_in:
            assert isinstance(for_in.target, cst.Name)
            names.add(for_in.target.value)
            for_in = for_in.inner_for_in
        metadata = self.get_metadata(cst.metadata.ScopeProvider, node)
        assert isinstance(metadata, cst.metadata.Scope)
        for name in names:
            if metadata._contains_in_self_or_parent(name):
                self.report(node, self.CUSTOM_MESSAGE.format(name=name))

    VALID = [
        Valid(
            """
            n = 1
            squares = [i ** 2 for i in range(10)]
            """
        ),
        Valid(
            """
            doubles = [i * 2 for i in range(10)]
            squares = [i ** 2 for i in range(10)]
            """
        ),
        Valid(
            """
            tags = ["a", "b", "c", "d"]
            entries = [["a", "b"],["c", "d"]]
            results = [lst for tag in tags for lst in entries if tag in lst]
            """
        ),
    ]

    INVALID = [
        Invalid(
            """
            def fn():
                return [i ** 2 for i in range(10)]

            i = 1
            """
        ),
        Invalid(
            """
            i = 1
            squares = [i ** 2 for i in range(10)]
            """
        ),
        Invalid(
            """
            i = 1

            def fn():
                return [i ** 2 for i in range(10)]
            """
        ),
        Invalid(
            """
            tags = ["a", "b", "c", "d"]
            entries = [["a", "b"],["c", "d"]]
            tag = "a"
            results = [lst for tag in tags for lst in entries if tag in lst]
            """
        ),
        Invalid(
            """
            tags = ["a", "b", "c", "d"]
            entries = [["a", "b"],["c", "d"]]
            lst = ["a", "b"]
            results = [lst for tag in tags for lst in entries if tag in lst]
            """
        ),
    ]
