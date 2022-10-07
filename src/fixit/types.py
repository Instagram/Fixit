# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from libcst._add_slots import add_slots
from libcst.metadata import CodeRange

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
    root: Path

    enable: List[str] = field(default_factory=lambda: ["fixit.rules"])
    disable: List[str] = field(default_factory=list)

    greeting: str = "hello"


@dataclass
class RawConfig:
    path: Path
    data: Dict[str, Any]


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
