# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from collections import defaultdict
from itertools import chain, islice
from typing import TYPE_CHECKING, Dict, Iterable, Mapping, Optional, Set

from libcst.metadata import FullRepoManager, TypeInferenceProvider


if TYPE_CHECKING:
    from libcst.metadata.base_provider import ProviderT


BATCH_SIZE: int = 100


PLACEHOLDER_CACHES: Dict["ProviderT", object] = {TypeInferenceProvider: {"types": []}}


def get_repo_caches(
    paths: Iterable[str],
    providers: Set["ProviderT"],
    timeout: int,
    repo_root_dir: str = "",
    batch_size: int = BATCH_SIZE,
) -> Mapping[str, Dict["ProviderT", object]]:
    """
    Generate type metadata by instantiating a :class:`~libcst.metadata.FullRepoManager` with
    :class:`~libcst.metadata.FullRepoManager` passed to ```providers``` parameter.

    :param paths: An iterable of paths to files to pass to :class:`~libcst.metadata.FullRepoManager` constructor's
    ```paths``` argument. These will be split in batches where the combined length of each path in the batch is <=
    ```arg_size```.

    :param timeout: The number of seconds at which to cap the pyre query which is run as a subprocess during cache resolving.

    :param repo_root_dir: Root directory of paths in ```paths```.

    :param batch_size: The size of the batch of paths to pass in each call to the :class:`~libcst.metadata.FullRepoManager` constructor.
    """
    caches = {}
    paths_iter = iter(paths)
    head: Optional[str] = next(paths_iter, None)
    while head is not None:
        paths_batch = tuple(chain([head], islice(paths_iter, batch_size - 1)))
        head = next(paths_iter, None)
        frm = FullRepoManager(
            repo_root_dir=repo_root_dir,
            paths=paths_batch,
            providers=providers,
            timeout=timeout,
        )
        try:
            # TODO: remove access of private variable when public `cache` property is available in libcst.metadata.FullRepoManager API.
            frm.resolve_cache()
            batch_caches = defaultdict(dict)
            for provider, files in frm._cache.items():
                for _path, cache in files.items():
                    batch_caches[_path][provider] = cache
            caches.update(batch_caches)
        except Exception:
            # Swallow any exceptions here. Since pyre is intrinsically unreliable, we don't want pyre-dependent rules
            # to break the linting process. When pyre fails, we put a placeholder cache, and the TypeInferenceProvider-
            # dependent lint rules will have reduced functionality / will not catch violations.
            # TODO: May want to extend `fixit.common.cli.ipc_main` functionality in the future to handle failures
            # that occur prior to the actual call to `lint_file`.
            caches.update(dict.fromkeys(paths_batch, PLACEHOLDER_CACHES))
    return caches
