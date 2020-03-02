# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import ast
import io
import tokenize
from pathlib import Path
from typing import Iterable

from libcst.testing.utils import UnitTest

from fixit.common.pseudo_rule import PseudoContext, PseudoLintRule
from fixit.common.report import BaseLintRuleReport
from fixit.rule_lint_engine import lint_file

DUMMY_FILE_PATH = Path(__file__)
DUMMY_SOURCE = b"pass\npass\npass\n"
DUMMY_LINT_CODE = "IG00"
DUMMY_LINT_MESSAGE = "dummy lint message"


class PseudoContextTest(UnitTest):
    ONCALL_SHORTNAME = "instagram_server_framework"

    def setUp(self) -> None:
        self.dummy_tokens = tuple(tokenize.tokenize(io.BytesIO(DUMMY_SOURCE).readline))
        self.dummy_ast_tree = ast.parse(DUMMY_SOURCE)

    def test_tokens(self) -> None:
        full_context = PseudoContext(
            file_path=DUMMY_FILE_PATH, source=DUMMY_SOURCE, tokens=self.dummy_tokens
        )
        self.assertIs(full_context.tokens, self.dummy_tokens)
        partial_context = PseudoContext(file_path=DUMMY_FILE_PATH, source=DUMMY_SOURCE)
        self.assertEqual(partial_context.tokens, self.dummy_tokens)
        self.assertIsNot(partial_context.tokens, self.dummy_tokens)

    def test_ast_tree(self) -> None:
        full_context = PseudoContext(
            file_path=DUMMY_FILE_PATH, source=DUMMY_SOURCE, ast_tree=self.dummy_ast_tree
        )
        self.assertIs(full_context.ast_tree, self.dummy_ast_tree)
        partial_context = PseudoContext(file_path=DUMMY_FILE_PATH, source=DUMMY_SOURCE)
        # partial_context.ast_tree should be equivalent to self.dummy_ast_tree
        self.assertIsNot(partial_context.ast_tree, self.dummy_ast_tree)


class PseudoLintRuleTest(UnitTest):
    ONCALL_SHORTNAME = "instagram_server_framework"

    def test_pseudo_lint_rule(self) -> None:
        class DummyLintRuleReport(BaseLintRuleReport):
            pass

        dummy_report = DummyLintRuleReport(
            file_path=DUMMY_FILE_PATH,
            code=DUMMY_LINT_CODE,
            message=DUMMY_LINT_MESSAGE,
            line=1,
            column=0,
        )

        class DummyPseudoLintRule(PseudoLintRule):
            def lint_file(self) -> Iterable[BaseLintRuleReport]:
                return [dummy_report]

        reports = lint_file(
            DUMMY_FILE_PATH, DUMMY_SOURCE, config={}, rules=[DummyPseudoLintRule]
        )
        self.assertEqual(reports, [dummy_report])
