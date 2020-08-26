# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
from libcst.codemod.commands.noop import NOOPCommand
from libcst.testing.utils import UnitTest

from fixit.cli.args import get_rule_parser


class SomeFakeRule:
    pass


class LintRuleCLIArgsTest(UnitTest):
    def test_rule_parser(self) -> None:
        parser = get_rule_parser().parse_args(
            ["fixit.cli.tests.test_args.SomeFakeRule"]
        )
        self.assertEqual(parser.rule, SomeFakeRule)

    def test_rule_parser_external_module(self) -> None:
        # External modules work, as long as they are a dependency
        parser = get_rule_parser().parse_args(
            ["libcst.codemod.commands.noop.NOOPCommand"]
        )
        self.assertEqual(parser.rule, NOOPCommand)
