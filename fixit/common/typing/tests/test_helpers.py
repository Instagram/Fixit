# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from itertools import chain
from pathlib import Path
from typing import Mapping
from unittest.mock import MagicMock, call, patch

from libcst.testing.utils import UnitTest

from fixit.common.typing.helpers import FilePathTooLongError, get_type_caches


class TypingHelpersTest(UnitTest):
    DUMMY_PATH = "fake/path.py"

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_get_type_caches_empty_paths(self, gen_cache: MagicMock) -> None:
        type_caches: Mapping[str, object] = get_type_caches([], 1)

        # We expect the call to resolve_cache to be bypassed.
        gen_cache.assert_not_called()
        self.assertEqual(type_caches, {})

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_get_type_caches_single_path(self, gen_cache: MagicMock) -> None:
        gen_cache.return_value = {self.DUMMY_PATH: {}}
        type_caches = get_type_caches((self.DUMMY_PATH,), 1)

        gen_cache.assert_called_with(Path(""), [self.DUMMY_PATH], 1)
        self.assertEqual(type_caches, {self.DUMMY_PATH: {}})

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_get_type_caches_max_length_respected(self, gen_cache: MagicMock) -> None:
        paths = [f"{idx}_" + p for idx, p in enumerate([self.DUMMY_PATH] * 5)]
        gen_cache.return_value = {}

        # Cap the arg_size at the length of each path in ```paths``` argument.
        arg_max = len(paths[0])
        get_type_caches(paths, 1, arg_size=arg_max)

        # A call to `gen_cache.__bool__()` will accompany every regular call to gen_cache() due to
        # the implementation of cache resolving in `libcst.metadata.FullRepoManager`.
        calls = chain.from_iterable(
            [(call.__bool__(), call(Path(""), [path], 1)) for path in paths]
        )

        # Expect a total of 10 calls to `gen_cache`.
        gen_cache.assert_has_calls(calls)

    @patch("libcst.metadata.TypeInferenceProvider.gen_cache")
    def test_throws_file_too_long_error(self, gen_cache: MagicMock) -> None:
        gen_cache.return_value = {}

        with self.assertRaises(FilePathTooLongError):
            # Cap the arg_size at length of the path minus one
            arg_max = len(self.DUMMY_PATH) - 1
            get_type_caches([self.DUMMY_PATH], 1, arg_size=arg_max)
