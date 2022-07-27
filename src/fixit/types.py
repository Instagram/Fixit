# Copyright (c) Meta Platforms, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

FileContent = bytes


@dataclass
class Options:
    """
    Command-line options to affect runtime behavior
    """

    debug: Optional[bool]
    config_file: Optional[Path]


@dataclass
class Config:
    """
    Materialized configuration valid for processing a single file
    """

    path: Path


@dataclass
class Result:
    """
    A single lint result for a given file and lint rule
    """

    path: Path
    error: Optional[Exception] = None
