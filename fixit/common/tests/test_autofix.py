# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Callable, Union

import libcst as cst
from libcst.metadata import CodePosition, MetadataWrapper
from libcst.testing.utils import data_provider, UnitTest

from fixit.common.autofix import LintPatch


class AutofixTest(UnitTest):
    @data_provider(
        {
            "full_module": {
                "original_module": "# hello, world\ndef foo(): ...\nbar()\n",
                "replacement_module": "val = 1 + 2\nraise Exception()\n",
                "get_original_node": lambda module: module,
                "get_replacement_node": lambda __: cst.parse_module(
                    "val = 1 + 2\nraise Exception()\n"
                ),
            },
            "full_module_noop": {
                "original_module": "# hello, world\ndef foo(): ...\nbar()\n",
                "replacement_module": "# hello, world\ndef foo(): ...\nbar()\n",
                "get_original_node": lambda module: module,
                "get_replacement_node": lambda module: module.deep_clone(),
            },
            "remove_statement": {
                "original_module": "first_line\nsecond_line\n",
                "replacement_module": "second_line\n",
                "get_original_node": lambda module: module.body[0],
                "get_replacement_node": lambda __: cst.RemovalSentinel.REMOVE,
            },
            "first_statement": {
                "original_module": "a\nb\n",
                "replacement_module": "new_statement()\nb\n",
                "get_original_node": lambda module: module.body[0],
                "get_replacement_node": lambda __: cst.parse_statement(
                    "new_statement()"
                ),
            },
            "first_expression": {
                "original_module": "old_fn()\nb\n",
                "replacement_module": "new_fn()\nb\n",
                "get_original_node": lambda module: module.body[0].body[0].value.func,
                "get_replacement_node": lambda __: cst.Name("new_fn"),
            },
            "last_statement": {
                "original_module": "a\nb",
                "replacement_module": "a\nnew_statement()",
                "get_original_node": lambda module: module.body[1],
                "get_replacement_node": lambda __: cst.parse_statement(
                    "new_statement()\n"
                ),
            },
            "last_expression": {
                "original_module": "a\none + two",
                "replacement_module": "a\none + new_value",
                "get_original_node": lambda module: module.body[1].body[0].value.right,
                "get_replacement_node": lambda __: cst.Name("new_value"),
            },
        }
    )
    def test_get(
        self,
        *,
        original_module: str,
        replacement_module: str,
        get_original_node: Callable[[cst.Module], cst.CSTNode],
        get_replacement_node: Callable[
            [cst.CSTNode], Union[cst.CSTNode, cst.RemovalSentinel]
        ],
    ) -> None:
        wrapper = MetadataWrapper(
            cst.parse_module(original_module), unsafe_skip_copy=True
        )
        n = get_original_node(wrapper.module)
        patch = LintPatch.get(wrapper, n, get_replacement_node(n))
        self.assertEqual(patch.apply(original_module), replacement_module)
        self.assertEqual(patch.minimize().apply(original_module), replacement_module)

    @data_provider(
        {
            "non_minimizable": {
                "before": LintPatch(0, CodePosition(1, 0), "foobar", "barfoo"),
                "after": LintPatch(0, CodePosition(1, 0), "foobar", "barfoo"),
            },
            "identical_tail": {
                "before": LintPatch(
                    0, CodePosition(1, 0), "hello, world!\n", "goodbye, world!\n"
                ),
                "after": LintPatch(0, CodePosition(1, 0), "hello", "goodbye"),
            },
            "identical_head": {
                "before": LintPatch(0, CodePosition(1, 0), "who", "what"),
                "after": LintPatch(2, CodePosition(1, 2), "o", "at"),
            },
            "newlines_lf": {
                "before": LintPatch(0, CodePosition(1, 0), "a\nb", "a\nc"),
                "after": LintPatch(2, CodePosition(2, 0), "b", "c"),
            },
            "newlines_cr": {
                "before": LintPatch(0, CodePosition(1, 0), "a\rb", "a\rc"),
                "after": LintPatch(2, CodePosition(2, 0), "b", "c"),
            },
            "newlines_crlf": {
                "before": LintPatch(0, CodePosition(1, 0), "a\r\nb", "a\r\nc"),
                "after": LintPatch(3, CodePosition(2, 0), "b", "c"),
            },
            "newlines_extended": {  # test a mix of multiple newlines in the same file
                "before": LintPatch(
                    0,
                    CodePosition(1, 0),
                    "a\r\nb\nc\rd\r\nis final",
                    "a\r\nb\nc\rd\r\nis last",
                ),
                "after": LintPatch(13, CodePosition(5, 3), "final", "last"),
            },
            "minimizable_noop": {  # should minimize to an empty patch
                "before": LintPatch(
                    0,
                    CodePosition(1, 0),
                    "This is\nsome\ncode\n",
                    "This is\nsome\ncode\n",
                ),
                "after": LintPatch(0, CodePosition(1, 0), "", ""),
            },
        }
    )
    def test_minimize(self, *, before: LintPatch, after: LintPatch) -> None:
        self.assertEqual(before.minimize(), after)
        # this should be a noop
        self.assertEqual(after.minimize(), after)
