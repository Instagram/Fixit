# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import subprocess
from pathlib import Path
from typing import Collection, Dict, Iterable, List, Tuple

from libcst.metadata import FullRepoManager, MetadataWrapper, TypeInferenceProvider
from libcst.metadata.base_provider import ProviderT

from fixit.common.config import FIXIT_ROOT, PYRE_TIMEOUT_SECONDS


_RepoTypeMetadata = Tuple[Dict[Path, "MetadataWrapper"], List[Path]]


def get_type_metadata(
    paths: Iterable[Path],
    timeout: int = PYRE_TIMEOUT_SECONDS,
    providers: Collection["ProviderT"] = {TypeInferenceProvider},
    repo_root_dir: str = str(FIXIT_ROOT),
) -> _RepoTypeMetadata:
    frm = FullRepoManager(
        repo_root_dir=repo_root_dir,
        paths=[str(path) for path in paths],
        providers=providers,
        timeout=timeout,
    )

    failed_paths: List[Path] = []
    repo_type_metadata: Dict[Path, "MetadataWrapper"] = {}

    for path in paths:
        try:
            repo_type_metadata[path] = frm.get_metadata_wrapper_for_path(path=str(path))
        except subprocess.TimeoutExpired:
            failed_paths.append(path)

    return (repo_type_metadata, failed_paths)
