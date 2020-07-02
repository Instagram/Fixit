# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import subprocess
from typing import Collection, Mapping

from libcst.metadata import FullRepoManager, TypeInferenceProvider

from fixit.common.config import FIXIT_ROOT


def get_type_caches(
    paths: Collection[str], timeout: int, repo_root_dir: str = str(FIXIT_ROOT),
) -> Mapping[str, object]:
    frm = FullRepoManager(
        repo_root_dir=repo_root_dir,
        paths=paths,
        providers={TypeInferenceProvider},
        timeout=timeout,
    )
    try:
        frm.resolve_cache()
        return frm._cache[TypeInferenceProvider]
    except subprocess.TimeoutExpired:
        # Swallow the timeout exception here. The expectation is that any rules that rely on Pyre data
        # throw an exception while they are running and each individual failure will be handled by the
        # lint rule engine further down the line.
        return {}
