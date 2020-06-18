# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import libcst as cst
from libcst.metadata import MetadataWrapper, TypeInferenceProvider
from libcst.metadata.type_inference_provider import PyreData
from libcst.testing.utils import UnitTest, data_provider

from fixit import rule_lint_engine
from fixit.common.base import CstLintRule
from fixit.common.config import FIXIT_ROOT
from fixit.common.testing import _dedent


class BadCallCstLintRule(CstLintRule):
    def visit_Call(self, node: cst.Call) -> None:
        func = node.func
        if isinstance(func, cst.Name) and func.value == "bad_call":
            self.report(node, "IG00 You made a bad call!")


class DummyTypingRule(CstLintRule):
    METADATA_DEPENDENCIES = (TypeInferenceProvider,)

    def visit_Name(self, node: cst.Name) -> None:
        if node in self.metadata[TypeInferenceProvider]:
            type_info = self.get_metadata(TypeInferenceProvider, node)
            if type_info == "typing.Type[typing.Any]":
                self.report(node, "IG00 Dummy message")


class ParenthesizeAttributeLintRule(CstLintRule):
    """
    Transforms the following code:

        obj.attr.another_attr

    into:

        ((obj.attr).another_attr)

    This serves as an easy test case for overlapping lint fixes.
    """

    def visit_Attribute(self, node: cst.Attribute) -> None:
        if len(node.lpar) == 0:
            new_node = node.with_changes(
                lpar=[cst.LeftParen()], rpar=[cst.RightParen()]
            )
            self.report(
                node,
                "IG00 All attributes should be parenthesized.",
                replacement=new_node,
            )


class RuleLintEngineTest(UnitTest):
    @data_provider(
        {
            "good_call": {
                "source": b"good_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": False,
                "expected_report_count": 0,
            },
            "bad_call": {
                "source": b"bad_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": False,
                "expected_report_count": 1,
            },
            "multiple_bad_calls": {
                "source": b"bad_call()\nbad_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": False,
                "expected_report_count": 2,
            },
            "bad_call_generated": {
                "source": b"'''@gen" + b"erated'''\nbad_call()",
                "use_ignore_byte_markers": True,
                "use_ignore_comments": False,
                "expected_report_count": 0,
            },
            "bad_call_noqa": {
                "source": b"bad_call()  # noqa\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": True,
                "expected_report_count": 0,
            },
            "bad_call_noqa_mixed": {
                "source": b"bad_call()  # noqa\nbad_call()  # missing noqa comment\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": True,
                "expected_report_count": 1,
            },
            "bad_call_noqa_file": {
                "source": b"# noqa-file: IG00: Test case\nbad_call()\nbad_call()\n",
                "use_ignore_byte_markers": False,
                "use_ignore_comments": True,
                "expected_report_count": 0,
            },
        }
    )
    def test_lint_file(
        self,
        *,
        source: bytes,
        use_ignore_byte_markers: bool,
        use_ignore_comments: bool,
        expected_report_count: int,
    ) -> None:
        reports = rule_lint_engine.lint_file(
            Path("dummy_filename.py"),
            source,
            use_ignore_byte_markers=use_ignore_byte_markers,
            use_ignore_comments=use_ignore_comments,
            config={},
            rules=[BadCallCstLintRule],
        )
        self.assertEqual(len(reports), expected_report_count)

    def test_lint_file_and_apply_patches(self) -> None:
        source = b"obj.attr.another_attr\n"
        expected_output = b"((obj.attr).another_attr)\n"

        result = rule_lint_engine.lint_file_and_apply_patches(
            Path("dummy_filename.py"),
            source,
            config={},
            rules=[ParenthesizeAttributeLintRule],
        )
        self.assertEqual(len(result.reports), 2)
        self.assertEqual(result.patched_source, expected_output)


class RuleLintEngineTestPyreIntegration(UnitTest):
    SOURCE_CODE = """
        from typing import Any, Type

        a: Type[Any]
        """

    # File containing Pyre typing output for the code in SOURCE_CODE
    PYRE_TYPES_FILE: Path = FIXIT_ROOT / "tests" / "helpers" / "pyre_types.json"

    @patch("libcst.metadata.FullRepoManager.get_metadata_wrapper_for_path")
    def test_type_inference_lint(self, mock_get_metadata: MagicMock) -> None:
        data: PyreData = json.loads(self.PYRE_TYPES_FILE.read_text())

        # We want to intercept any calls that will require the pyre engine to be running
        fake_metadata_wrapper = MetadataWrapper(
            module=cst.parse_module(_dedent(self.SOURCE_CODE)),
            # pyre-ignore[6]: Expected `typing.Mapping[typing.Type[cst.metadata.base_provider.BaseMetadataProvider[object]], object]`
            # for 2nd parameter `cache` to call `cst.metadata.wrapper.MetadataWrapper.__init__` but got
            # `typing.Dict[typing.Type[cst.metadata.type_inference_provider.TypeInferenceProvider], TypedDict `PyreData`]`.
            cache={TypeInferenceProvider: data},
        )

        mock_get_metadata.return_value = fake_metadata_wrapper

        reports = rule_lint_engine.lint_file(
            Path("dummy_filepath.py"),
            source=str.encode(_dedent(self.SOURCE_CODE)),
            config={},
            rules=[DummyTypingRule],
        )

        # We're expecting DummyTypingRule to raise one lint error
        self.assertEqual(len(reports), 1)

    @patch("pathlib.Path.read_text")
    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_type_inference_lint_with_timeout(
        self, mock_gen_cache: MagicMock, mock_read_text: MagicMock
    ) -> None:
        # Here we assume the TypeInferenceProvider works as expected and throws a timeout exception if
        # the `pyre query` command takes longer than the supplied value. We just want to make sure we
        # handle the timeout gracefully on our side
        mock_gen_cache.side_effect = subprocess.TimeoutExpired(
            cmd="pyre check ...", timeout=0
        )

        # We also want to patch Path.read_text() since we're passing in a fake file path
        mock_read_text.return_value = _dedent(self.SOURCE_CODE)

        # Pass 0 seconds as the timeout value
        reports = rule_lint_engine.lint_file(
            file_path=Path("doesntmatterwhatiputhere.py"),
            # It doesn't actually matter what we pass as the source here since we are expecting a timeout error
            source=b"a = 1",
            config={},
            rules=[DummyTypingRule],
            timeout=0,
        )

        # Currently, we expect lint_file to swallow any TimeoutExpired exception.
        self.assertEqual(len(reports), 0)
