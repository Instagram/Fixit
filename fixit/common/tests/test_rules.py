# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from libcst.testing.utils import (  # noqa IG69: this module is only used by tests
    UnitTest,
)

from fixit.rule_lint_engine import get_rules


class TestsForAllLintRules(UnitTest):
    ONCALL_SHORTNAME = "instagram_server_framework"

    def test_rule_has_oncall(self) -> None:
        failures = []
        for rule in get_rules():
            if getattr(rule, "ONCALL_SHORTNAME", None) is None:
                failures.append(
                    f"{rule.__name__} has no ONCALL_SHORTNAME set, "
                    + "please add one by setting ONCALL_SHORTNAME to your oncall's email: "
                    + "https://fburl.com/igsrv_oncall_shortname_examples "
                    + "(if you're having trouble finding your oncall, try `i oncall` "
                    + "in bunnylol or `oncall_shifts list $USER`)"
                )
                continue

        self.assertEqual(failures, [])
