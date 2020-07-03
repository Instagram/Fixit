# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from itertools import chain, islice
from typing import Iterable, Mapping

from libcst.metadata import FullRepoManager, TypeInferenceProvider


BATCH_SIZE: int = 1000


def get_type_caches(
    paths: Iterable[str], timeout: int, repo_root_dir: str, batch_size: int = BATCH_SIZE
) -> Mapping[str, object]:
    caches = {}
    paths_iterator = iter(paths)
    for first in paths_iterator:
        # We want to pass paths to `FullRepoManager` in batches otherwise we run the risk of `TypeInferenceProvider`
        # being unable to handle too many files.
        paths_batch = tuple(chain([first], islice(paths_iterator, batch_size - 1)))
        frm = FullRepoManager(
            repo_root_dir=repo_root_dir,
            paths=paths_batch,
            providers={TypeInferenceProvider},
            timeout=timeout,
        )
        try:
            # TODO: Once LibCST TypeInferenceProvider API is updated, replace this access of a private
            # variable with new API method.
            frm.resolve_cache()
            caches.update(frm._cache[TypeInferenceProvider])
        except Exception:
            # Swallow any exceptions here. The expectation is that any rules that rely on Pyre data will
            # raise an exception during the lint and each failure will be handled by the lint engine.
            # TODO: May want to extend `fixit.common.cli.ipc_main` functionality in the future to handle failures
            # that occur prior to the actual call to `lint_file`.
            caches.update(dict.fromkeys(paths_batch, None))
    return caches
