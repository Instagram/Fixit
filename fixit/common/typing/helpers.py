# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Iterable, Mapping, Optional

from libcst.metadata import FullRepoManager, TypeInferenceProvider


ARG_MAX: int = 100000


class FilePathTooLongError(Exception):
    pass


def get_type_caches(
    paths: Iterable[str], timeout: int, repo_root_dir: str = "", arg_size: int = ARG_MAX
) -> Mapping[str, object]:
    """
    Generate type metadata by instantiating a :class:`~libcst.metadata.FullRepoManager` with
    :class:`~libcst.metadata.FullRepoManager` passed to ```providers``` parameter.

    :param paths: An iterable of paths to files to pass to :class:`~libcst.metadata.FullRepoManager` constructor's
    ```paths``` argument. These will be split in batches where the combined length of each path in the batch is <=
    ```arg_size```.

    :param timeout: The number of seconds at which to cap the pyre query which is run as a subprocess during cache resolving.

    :param repo_root_dir: Root directory of paths in ```paths```.

    :param arg_size: The length at which to cap the string argument that will be passed to the ```args``` parameter of the
    :class:`~subprocess.Popen` constructor. To avoid shell error due to argument exceeding max allowable length. The maximum
    size for a single string argument passed to the shell is system-dependent.
    """
    caches = {}
    paths_iter = iter(paths)
    head: Optional[str] = next(paths_iter, None)
    while head is not None:
        paths_batch = []
        remaining = arg_size
        if len(head) > remaining:
            raise FilePathTooLongError(
                f"The file path name `{head}` is longer than the maximum name length: {arg_size}."
            )
        while head is not None and remaining - len(head) >= 0:
            remaining -= len(head)
            paths_batch.append(head)
            head = next(paths_iter, None)
        frm = FullRepoManager(
            repo_root_dir=repo_root_dir,
            paths=paths_batch,
            providers={TypeInferenceProvider},
            timeout=timeout,
        )
        try:
            # TODO: replace access of private variable when updated libcst.metadata.FullRepoManager API is available.
            frm.resolve_cache()
            caches.update(frm._cache[TypeInferenceProvider])
        except Exception:
            # Swallow any exceptions here. The expectation is that any rules that rely on Pyre data will
            # raise an exception during the lint and each failure will be handled by the lint engine.
            # TODO: May want to extend `fixit.common.cli.ipc_main` functionality in the future to handle failures
            # that occur prior to the actual call to `lint_file`.
            caches.update(dict.fromkeys(paths_batch, None))
    return caches
