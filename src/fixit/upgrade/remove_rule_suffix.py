# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst
from libcst.metadata import FullyQualifiedNameProvider

from fixit import Invalid, LintRule, Valid


class FixitRemoveRuleSuffix(LintRule):
    """
    Remove the "Rule" suffix from lint rule class names
    """

    MESSAGE = "Do not end lint rule subclasses with 'Rule'"
    METADATA_DEPENDENCIES = (FullyQualifiedNameProvider,)

    VALID = [
        Valid(
            """
            import fixit
            class DontTryThisAtHome(fixit.LintRule): ...
            """
        ),
        Valid(
            """
            from fixit import LintRule
            class CatsRuleDogsDrool(LintRule): ...
            """
        ),
        Valid(
            """
            class NotALintRule: ...
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            import fixit
            class DontTryThisAtHomeRule(fixit.LintRule): ...
            """
        ),
        Invalid(
            """
            from fixit import LintRule
            class CatsRuleDogsDroolRule(LintRule): ...
            """
        ),
    ]

    def visit_ClassDef(self, node: libcst.ClassDef) -> None:
        for base in node.bases:
            metadata = self.get_metadata(FullyQualifiedNameProvider, base.value)
            if isinstance(metadata, set):
                qname = metadata.pop().name
                if qname == "fixit.LintRule":
                    rule_name = node.name.value
                    if rule_name.endswith("Rule"):
                        rep = node.name.with_changes(value=rule_name[:-4])
                        self.report(node.name, replacement=rep)
