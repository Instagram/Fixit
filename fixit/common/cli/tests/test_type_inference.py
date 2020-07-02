# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import subprocess
from pathlib import Path
from typing import Collection, List, Mapping, Optional, Type, Union, cast
from unittest.mock import MagicMock, mock_open, patch

import libcst as cst
from libcst.metadata import BaseMetadataProvider, MetadataWrapper, TypeInferenceProvider
from libcst.testing.utils import UnitTest

from fixit.common.base import CstContext, CstLintRule, LintRuleT
from fixit.common.cli import LintWorkers, map_paths
from fixit.common.report import BaseLintRuleReport
from fixit.common.typing.helpers import get_type_caches
from fixit.rule_lint_engine import lint_file


SOURCE_CODE = b"class Foo: pass"


class DummyTypingRule(CstLintRule):
    METADATA_DEPENDENCIES = (TypeInferenceProvider,)

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)

    def visit_Module(self, node: cst.Module) -> None:
        self.report(node, "IG00 dummy message")


def _lint_file_caller_func(
    path: Path, config: List[LintRuleT], type_cache: Optional[object],
) -> Union[str, Collection[BaseLintRuleReport]]:
    cst_wrapper = None
    try:
        if type_cache is not None:
            cst_wrapper = MetadataWrapper(
                cst.parse_module(SOURCE_CODE),
                True,
                {
                    cast(
                        Type[BaseMetadataProvider[object]], TypeInferenceProvider
                    ): type_cache
                },
            )
        return lint_file(
            file_path=path, source=SOURCE_CODE, rules=config, cst_wrapper=cst_wrapper,
        )
    except Exception as e:
        return str(e)


class TypeInferenceTest(UnitTest):
    DUMMY_PATH: Path = Path(__file__)

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_basic_type_inference(self, mock_gen_cache: MagicMock) -> None:
        # We want to intercept any calls that will require the pyre engine to be running
        fake_cache = {
            str(self.DUMMY_PATH): {
                "types": [
                    {
                        "location": {
                            "start": {"line": 0, "column": 0},
                            "stop": {"line": 0, "column": 0},
                        },
                        "annotation": "typing.Any",
                    },
                ],
            }
        }

        mock_gen_cache.return_value = fake_cache

        type_caches: Mapping[str, object] = get_type_caches([str(self.DUMMY_PATH)], 1)

        mock_operation: MagicMock = MagicMock(side_effect=_lint_file_caller_func)

        reports = next(
            map_paths(
                operation=mock_operation,
                paths=[str(self.DUMMY_PATH)],
                config=[DummyTypingRule],
                workers=LintWorkers.USE_CURRENT_THREAD,
                type_caches=type_caches,
            )
        )

        mock_operation.assert_called_with(
            self.DUMMY_PATH, [DummyTypingRule], type_caches[str(self.DUMMY_PATH)]
        )

        self.assertEqual(len(reports), 1)

    @patch("builtins.open", new_callable=mock_open, read_data=SOURCE_CODE)
    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_type_inference_with_timeout(self, mock_gen_cache: MagicMock, _) -> None:
        timeout = 1
        timeout_error = subprocess.TimeoutExpired(cmd="pyre query ...", timeout=timeout)
        mock_gen_cache.side_effect = timeout_error

        type_caches = get_type_caches(paths=[str(self.DUMMY_PATH)], timeout=timeout)
        mock_operation: MagicMock = MagicMock(side_effect=_lint_file_caller_func)

        # We're expecting this type-dependent lint rule to raise an Exception since it does not
        # have access to a cache of inferred types.
        expected_error_message: str = "Cache is required for initializing TypeInferenceProvider."

        report = next(
            map_paths(
                operation=mock_operation,
                paths=[str(self.DUMMY_PATH)],
                config=[DummyTypingRule],
                workers=LintWorkers.USE_CURRENT_THREAD,
                type_caches=type_caches,
            )
        )

        mock_operation.assert_called_with(self.DUMMY_PATH, [DummyTypingRule], None)

        self.assertEqual(report, expected_error_message)
