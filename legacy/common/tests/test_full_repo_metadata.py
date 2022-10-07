# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
from collections import defaultdict
from itertools import chain
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Dict, Mapping
from unittest.mock import call, MagicMock, patch

from libcst.metadata import TypeInferenceProvider
from libcst.metadata.base_provider import ProviderT
from libcst.testing.utils import UnitTest

from fixit.common.full_repo_metadata import FullRepoMetadataConfig, get_repo_caches


class FullRepoMetadataTest(UnitTest):
    DUMMY_PATH = "fake/path.py"

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_get_repo_caches_empty_paths(self, gen_cache: MagicMock) -> None:
        repo_caches: Mapping[str, Dict[ProviderT, object]] = get_repo_caches(
            [], FullRepoMetadataConfig({TypeInferenceProvider}, 1)
        )

        # We expect the call to resolve_cache to be bypassed.
        gen_cache.assert_not_called()
        self.assertEqual(repo_caches, {})

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_get_repo_caches_single_path(self, gen_cache: MagicMock) -> None:
        gen_cache.return_value = {self.DUMMY_PATH: {}}
        repo_caches = get_repo_caches(
            (self.DUMMY_PATH,), FullRepoMetadataConfig({TypeInferenceProvider}, 1)
        )

        gen_cache.assert_called_with(Path(""), [self.DUMMY_PATH], 1)
        self.assertEqual(repo_caches, {self.DUMMY_PATH: {TypeInferenceProvider: {}}})

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_get_repo_caches_swallows_exception(self, gen_cache: MagicMock) -> None:
        gen_cache.side_effect = Exception()
        repo_caches = get_repo_caches(
            (self.DUMMY_PATH,), FullRepoMetadataConfig({TypeInferenceProvider}, 1)
        )

        gen_cache.assert_called_with(Path(""), [self.DUMMY_PATH], 1)
        # Assert the placeholder cache is returned in the event of an error.
        self.assertEqual(
            repo_caches, {self.DUMMY_PATH: {TypeInferenceProvider: {"types": []}}}
        )

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_get_repo_caches_honors_batch_size(self, gen_cache: MagicMock) -> None:
        paths = [f"{idx}_" + p for idx, p in enumerate([self.DUMMY_PATH] * 5)]
        gen_cache.return_value = {}

        get_repo_caches(
            paths, FullRepoMetadataConfig({TypeInferenceProvider}, 1, batch_size=2)
        )

        # A call to `gen_cache.__bool__()` will accompany every regular call to gen_cache() due to
        # the implementation of cache resolving in `libcst.metadata.FullRepoManager`.
        calls = [
            call(Path(""), paths[:2], 1),
            call(Path(""), paths[2:4], 1),
            call(Path(""), [paths[4]], 1),
        ]
        all_calls = chain.from_iterable([(call.__bool__(), c) for c in calls])

        # pyre-fixme[6]: Expected `Sequence[unittest.mock._Call]` for 1st param but
        #  got `Iterator[typing.Any]`.
        gen_cache.assert_has_calls(all_calls)

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_get_repo_caches_with_logger(self, gen_cache: MagicMock) -> None:
        gen_cache.side_effect = TimeoutExpired("pyre query ...", 1)
        logger = logging.getLogger("Test")

        class CustomHandler(logging.Handler):
            errors = defaultdict(list)

            def emit(self, record: logging.LogRecord) -> None:
                exception_type = record.exc_info[0]
                self.errors[exception_type] += record.__dict__["paths"]

        hdlr = CustomHandler()
        logger.addHandler(hdlr)
        get_repo_caches(
            [self.DUMMY_PATH],
            FullRepoMetadataConfig(
                {TypeInferenceProvider}, 1, batch_size=2, logger=logger
            ),
        )

        self.assertEqual(CustomHandler.errors, {TimeoutExpired: [self.DUMMY_PATH]})
