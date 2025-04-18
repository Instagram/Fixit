# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Dict, Sequence, Tuple

import libcst
from libcst._nodes.statement import ImportFrom
from libcst.metadata import FullyQualifiedNameProvider

from fixit import Invalid, LintRule, Valid


class FixitDeprecatedImport(LintRule):
    """
    Upgrade lint rules to replace deprecated imports with their replacements.
    """

    MESSAGE = "Fixit deprecated import {old_name}, use {new_name} instead"
    METADATA_DEPENDENCIES = (FullyQualifiedNameProvider,)

    DEPRECATIONS: Dict[str, Tuple[str, str]] = {
        "fixit.CstLintRule": ("CstLintRule", "LintRule"),
        "fixit.CSTLintRule": ("CSTLintRule", "LintRule"),
        "fixit.InvalidTestCase": ("InvalidTestCase", "Invalid"),
        "fixit.ValidTestCase": ("ValidTestCase", "Valid"),
    }

    VALID = [
        Valid("from fixit import LintRule"),
        Valid("from fixit import Invalid"),
        Valid("from fixit import Valid"),
    ]
    INVALID = [
        Invalid(
            "from fixit import CstLintRule",
            expected_replacement="from fixit import LintRule",
        ),
        Invalid(
            "from fixit import CSTLintRule",
            expected_replacement="from fixit import LintRule",
        ),
        Invalid(
            "from fixit import InvalidTestCase",
            expected_replacement="from fixit import Invalid",
        ),
        Invalid(
            "from fixit import InvalidTestCase as Invalid",
            expected_replacement="from fixit import Invalid",
        ),
        Invalid(
            "from fixit import ValidTestCase as Valid",
            expected_replacement="from fixit import Valid",
        ),
        Invalid(
            """
            from fixit import (
                CstLintRule,
                InvalidTestCase as Invalid,
                ValidTestCase,
            )

            class FakeThing(CstLintRule):
                VALID = [
                    ValidTestCase(""),
                ]
                INVALID = [
                    Invalid(""),
                ]
            """,
            expected_replacement="""
            from fixit import (
                LintRule,
                Invalid,
                Valid,
            )

            class FakeThing(LintRule):
                VALID = [
                    Valid(""),
                ]
                INVALID = [
                    Invalid(""),
                ]
            """,
        ),
    ]

    def visit_ImportFrom(self, node: ImportFrom) -> None:
        if isinstance(node.module, libcst.Name) and isinstance(node.names, Sequence):
            module = node.module.value

            # pyrefly: ignore  # not-iterable
            for alias in node.names:
                fqname = f"{module}.{alias.name.value}"

                if fqname in self.DEPRECATIONS:
                    old_name, new_name = self.DEPRECATIONS[fqname]
                    rep = alias.with_changes(
                        name=alias.name.with_changes(value=new_name)
                    )

                    # don't keep 'Name as Name'
                    if (
                        alias.asname
                        and isinstance(alias.asname.name, libcst.Name)
                        and alias.asname.name.value == new_name
                    ):
                        rep = rep.with_changes(asname=None)

                    self.report(
                        alias,
                        self.MESSAGE.format(old_name=old_name, new_name=new_name),
                        replacement=rep,
                    )

    def visit_Name(self, node: libcst.Name) -> None:
        metadata = self.get_metadata(FullyQualifiedNameProvider, node)
        if isinstance(metadata, set) and metadata:
            fqname = metadata.pop().name

            if fqname in self.DEPRECATIONS:
                old_name, new_name = self.DEPRECATIONS[fqname]

                if node.value == old_name:
                    rep = node.with_changes(value=new_name)
                    self.report(
                        node,
                        self.MESSAGE.format(old_name=old_name, new_name=new_name),
                        replacement=rep,
                    )
