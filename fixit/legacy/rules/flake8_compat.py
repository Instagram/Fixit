# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Iterable

from fixit.common.flake8_compat import (
    Flake8LintRuleReport,
    get_cached_application_instance,
)
from fixit.common.pseudo_rule import PseudoLintRule


class Flake8PseudoLintRule(PseudoLintRule):
    """
    Executes all of flake8 under our lint engine as if it was a typical lint rule. This
    uses a bunch of internal flake8 APIs, so it's fragile and could break between
    releases of flake8.
    """

    def lint_file(self) -> Iterable[Flake8LintRuleReport]:
        app = get_cached_application_instance()
        app.reset(self.context)
        # TODO: use self.context.source, self.context.tokens, and self.context.ast
        app.run_checks([str(self.context.file_path)])
        # when we call report, it'll store the results to app.accumulator
        app.report()

        result = []
        for violation in app.accumulator:
            result.append(
                Flake8LintRuleReport(
                    file_path=self.context.file_path,
                    code=violation.code,
                    message=violation.text,
                    line=violation.line_number,
                    column=violation.column_number,
                )
            )

        return result
