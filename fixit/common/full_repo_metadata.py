# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from collections import defaultdict
from dataclasses import dataclass
from itertools import chain, islice
from typing import Dict, Iterable, Mapping, Optional, Set, TYPE_CHECKING

from libcst.metadata import FullRepoManager, TypeInferenceProvider


if TYPE_CHECKING:
    from logging import Logger

    from libcst.metadata.base_provider import ProviderT


BATCH_SIZE: int = 100


PLACEHOLDER_CACHES: Dict["ProviderT", object] = {TypeInferenceProvider: {"types": []}}


@dataclass(frozen=True)
class FullRepoMetadataConfig:
    providers: Set["ProviderT"]
    timeout_seconds: int
    repo_root_dir: str = ""
    batch_size: int = BATCH_SIZE
    logger: Optional["Logger"] = None


def get_repo_caches(
    paths: Iterable[str],
    config: FullRepoMetadataConfig,
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
        paths_batch = tuple(chain([head], islice(paths_iter, config.batch_size - 1)))
        head = next(paths_iter, None)
        frm = FullRepoManager(
            repo_root_dir=config.repo_root_dir,
            paths=paths_batch,
            providers=config.providers,
            timeout=config.timeout_seconds,
        )
        try:
            frm.resolve_cache()
        except Exception:
            # We want to fail silently since some metadata providers can be flaky. If a logger is provided by the caller, we'll add a log here.
            logger = config.logger
            if logger is not None:
                logger.warning(
                    "Failed to retrieve metadata cache.",
                    exc_info=True,
                    extra={"paths": paths_batch},
                )
            # Populate with placeholder caches to avoid failures down the line. This will however result in reduced functionality in cache-dependent lint rules.
            caches.update(
                dict.fromkeys(
                    paths_batch,
                    {
                        provider: PLACEHOLDER_CACHES[provider]
                        for provider in config.providers
                    },
                )
            )
        else:
            # TODO: remove access of private variable when public `cache` property is available in libcst.metadata.FullRepoManager API.
            batch_caches = defaultdict(dict)
            for provider, files in frm._cache.items():
                for _path, cache in files.items():
                    batch_caches[_path][provider] = cache
            caches.update(batch_caches)
    return caches
