# Copyright (c) Meta Platforms, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path

from .types import Config


def generate_config(path: Path) -> Config:
    """
    Given a file path, walk upwards looking for and applying cascading configs
    """
    path = path.resolve()

    return Config(
        path=path,
    )
