# Copyright (c) Meta Platforms, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from libcst.metadata import CodeRange
from libcst._add_slots import add_slots

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


@add_slots
@dataclass(frozen=True)
class LintViolation:
    rule_name: str
    range: CodeRange
    message: str
    autofixable: bool


@dataclass
class Result:
    """
    A single lint result for a given file and lint rule
    """

    path: Path
    violation: Optional[LintViolation]
    error: Optional[Exception] = None
