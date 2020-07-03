# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import subprocess
from pathlib import Path
from typing import Collection, List, Mapping, Optional, Type, Union, cast
from unittest.mock import MagicMock, patch

import libcst as cst
from libcst.metadata import BaseMetadataProvider, MetadataWrapper, TypeInferenceProvider
from libcst.testing.utils import UnitTest

from fixit.common.base import CstLintRule, LintRuleT
from fixit.common.cli import LintWorkers, map_paths
from fixit.common.config import FIXIT_ROOT
from fixit.common.report import BaseLintRuleReport
from fixit.common.typing.helpers import get_type_caches
from fixit.rule_lint_engine import lint_file


SOURCE_CODE = b"class Foo: pass"


class DummyTypeDependentRule(CstLintRule):
    METADATA_DEPENDENCIES = (TypeInferenceProvider,)

    def visit_Module(self, node: cst.Module) -> None:
        self.report(node, "IG00 dummy message")


def map_paths_operation(
    path: Path, config: List[LintRuleT], type_cache: Optional[object],
) -> Union[str, Collection[BaseLintRuleReport]]:
    # A top-level function to be accessible by `map_paths` from `fixit.common.cli`.
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
    DUMMY_PATH: Path = Path("fake/path.py")
    DUMMY_PATH_2: Path = Path("fake/path_2.py")

    def setUp(self) -> None:
        self.mock_operation: MagicMock = MagicMock(side_effect=map_paths_operation)
        self.fake_pyre_data: object = {
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

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_basic_type_inference(self, gen_cache: MagicMock) -> None:
        # We want to intercept any calls that will require the pyre engine to be running.
        gen_cache.return_value = {str(self.DUMMY_PATH): self.fake_pyre_data}
        paths = [str(self.DUMMY_PATH)]
        type_caches: Mapping[str, object] = get_type_caches(paths, 1, str(FIXIT_ROOT))

        reports = next(
            map_paths(
                operation=self.mock_operation,
                paths=paths,
                config=[DummyTypeDependentRule],
                workers=LintWorkers.USE_CURRENT_THREAD,
                type_caches=type_caches,
            )
        )

        self.mock_operation.assert_called_with(
            self.DUMMY_PATH, [DummyTypeDependentRule], type_caches[str(self.DUMMY_PATH)]
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].file_path, self.DUMMY_PATH)

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_basic_type_inference_multiple_paths(self, gen_cache: MagicMock) -> None:
        paths: List[str] = [str(self.DUMMY_PATH), str(self.DUMMY_PATH_2)]
        gen_cache.return_value = {path: self.fake_pyre_data for path in paths}

        type_caches: Mapping[str, object] = get_type_caches(paths, 1, str(FIXIT_ROOT))

        all_reports = map_paths(
            operation=self.mock_operation,
            paths=paths,
            config=[DummyTypeDependentRule],
            workers=LintWorkers.USE_CURRENT_THREAD,
            type_caches=type_caches,
        )

        # Reports should be returned in order since we specified `LintWorkers.USE_CURRENT_THREAD`.
        for i, reports in enumerate(all_reports):
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].file_path, Path(paths[i]))

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_type_inference_with_timeout(self, gen_cache: MagicMock) -> None:
        timeout = 1
        timeout_error = subprocess.TimeoutExpired(cmd="pyre query ...", timeout=timeout)
        gen_cache.side_effect = timeout_error

        # We're expecting this type-dependent lint rule to raise an Exception since it does not
        # have access to a cache of inferred types. This exception should be handled in `mock_operation`.
        expected_error_message: str = "Cache is required for initializing TypeInferenceProvider."
        paths: List[str] = [str(self.DUMMY_PATH)]
        type_caches = get_type_caches(paths, timeout, str(FIXIT_ROOT))

        report = next(
            map_paths(
                operation=self.mock_operation,
                paths=paths,
                config=[DummyTypeDependentRule],
                workers=LintWorkers.USE_CURRENT_THREAD,
                type_caches=type_caches,
            )
        )

        self.mock_operation.assert_called_with(
            self.DUMMY_PATH, [DummyTypeDependentRule], None
        )

        self.assertEqual(report, expected_error_message)
