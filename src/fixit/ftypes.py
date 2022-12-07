# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TypeVar, Union

from libcst._add_slots import add_slots
from libcst.metadata import CodePosition as CSTCodePosition, CodeRange as CSTCodeRange

T = TypeVar("T")

FileContent = bytes
RuleOptionTypes = (str, int, float)
RuleOptions = Dict[str, Union[str, int, float]]
RuleOptionsTable = Dict[str, RuleOptions]
CodeRange = CSTCodeRange
CodePosition = CSTCodePosition

QualifiedRuleRegex = re.compile(
    r"""
    ^
    (?P<local>\.)?
    (?P<module>[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*)
    (?::(?P<name>[a-zA-Z0-9_]+))?
    $
    """,
    re.VERBOSE,
)


def is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def is_collection(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes))


@dataclass(frozen=True, order=True)
class QualifiedRule:
    module: str
    name: Optional[str] = None
    local: Optional[str] = None
    root: Optional[Path] = field(default=None, hash=False, compare=False, repr=False)

    def __str__(self) -> str:
        return (
            ("." if self.local else "")
            + self.module
            + (f":{self.name}" if self.name else "")
        )


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

    enable: List[QualifiedRule] = field(
        default_factory=lambda: [QualifiedRule("fixit.rules")]
    )
    disable: List[QualifiedRule] = field(default_factory=list)
    options: RuleOptionsTable = field(default_factory=dict)

    def __post_init__(self):
        self.path = self.path.resolve()
        self.root = self.root.resolve()


@dataclass
class RawConfig:
    path: Path
    data: Dict[str, Any]

    def __post_init__(self):
        self.path = self.path.resolve()


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
    error: Optional[Tuple[Exception, str]] = None
