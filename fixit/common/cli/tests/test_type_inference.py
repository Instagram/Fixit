# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import subprocess
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock, patch

import libcst as cst
from libcst.metadata import MetadataWrapper, TypeInferenceProvider
from libcst.testing.utils import UnitTest

from fixit.common.base import CstLintRule, LintRuleT
from fixit.common.cli import LintWorkers, map_paths
from fixit.common.typing.helpers import get_type_metadata
from fixit.rule_lint_engine import lint_file


SOURCE_CODE = b"class Foo: pass"


class DummyTypingRule(CstLintRule):
    pass


def _lint_file_caller_func(
    path: Path,
    config: List[LintRuleT],
    metadata_wrapper_for_path: Optional[MetadataWrapper],
) -> None:
    lint_file(
        file_path=path,
        source=SOURCE_CODE,
        rules=config,
        cst_wrapper=metadata_wrapper_for_path,
    )


class TypeInferenceTest(UnitTest):
    DUMMY_PATH: Path = Path(__file__)

    @patch("libcst.metadata.FullRepoManager.get_metadata_wrapper_for_path")
    def test_basic_type_inference(self, mock_get_metadata: MagicMock) -> None:
        # We want to intercept any calls that will require the pyre engine to be running
        fake_metadata_wrapper = MetadataWrapper(
            module=cst.parse_module(SOURCE_CODE),
            unsafe_skip_copy=True,
            # pyre-ignore[6]: Expected `typing.Mapping[typing.Type[cst.metadata.base_provider.BaseMetadataProvider[object]], object]`
            # for 2nd parameter `cache` to call `cst.metadata.wrapper.MetadataWrapper.__init__` but got
            # `typing.Dict[typing.Type[cst.metadata.type_inference_provider.TypeInferenceProvider], TypedDict `PyreData`]`.
            cache={
                TypeInferenceProvider: {
                    "types": [
                        {
                            "location": {
                                "start": {"line": 0, "column": 0},
                                "stop": {"line": 0, "column": 0},
                            },
                            "annotation": "typing.Any",
                        },
                    ]
                }
            },
        )

        mock_get_metadata.return_value = fake_metadata_wrapper

        type_metadata = get_type_metadata([self.DUMMY_PATH])

        mock_operation: MagicMock = MagicMock(side_effect=_lint_file_caller_func)

        next(
            map_paths(
                operation=mock_operation,
                paths=[self.DUMMY_PATH],
                config=[DummyTypingRule],
                workers=LintWorkers.USE_CURRENT_THREAD,
                metadata_wrappers=type_metadata,
            )
        )

        mock_operation.assert_called_with(
            self.DUMMY_PATH, [DummyTypingRule], type_metadata[self.DUMMY_PATH]
        )

    @patch("fixit.common.typing.helpers.format_and_print_pyre_warnings")
    @patch("libcst.metadata.FullRepoManager.get_metadata_wrapper_for_path")
    def test_type_inference_with_timeout(
        self, mock_get_metadata: MagicMock, mock_print_pyre_warnings: MagicMock
    ) -> None:
        timeout = 1
        timeout_error = subprocess.TimeoutExpired(
            cmd=f"pyre query \"types(path='{self.DUMMY_PATH}')\"", timeout=timeout
        )
        mock_get_metadata.side_effect = timeout_error

        get_type_metadata(paths=[self.DUMMY_PATH], timeout=timeout)

        mock_print_pyre_warnings.assert_called_with([timeout_error.cmd])
