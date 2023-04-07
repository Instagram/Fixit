# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    ContextManager,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
)

from libcst import CSTNode, FlattenSentinel, RemovalSentinel
from libcst._add_slots import add_slots
from libcst.metadata import CodePosition as CodePosition, CodeRange as CodeRange

T = TypeVar("T")

CodeRange
CodePosition

FileContent = bytes
RuleOptionTypes = (str, int, float)
RuleOptions = Dict[str, Union[str, int, float]]
RuleOptionsTable = Dict[str, RuleOptions]

NodeReplacement = Union[CSTNode, FlattenSentinel, RemovalSentinel]

Timings = Dict[str, int]
TimingsHook = Callable[[Timings], None]

VisitorMethod = Callable[[CSTNode], None]
VisitHook = Callable[[str], ContextManager]


@dataclass(frozen=True)
class InvalidTestCase:
    code: str
    range: Optional[CodeRange] = None
    expected_message: Optional[str] = None
    expected_replacement: Optional[str] = None


@dataclass(frozen=True)
class ValidTestCase:
    code: str


QualifiedRuleRegex = re.compile(
    r"""
    ^
    (?P<module>
        (?P<local>\.)?
        [a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*
    )
    (?::(?P<name>[a-zA-Z0-9_]+))?
    $
    """,
    re.VERBOSE,
)


class QualifiedRuleRegexResult(TypedDict):
    module: str
    name: Optional[str]
    local: Optional[str]


def is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def is_collection(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes))


@dataclass(frozen=True)
class QualifiedRule:
    module: str
    name: Optional[str] = None
    local: Optional[str] = None
    root: Optional[Path] = field(default=None, hash=False, compare=False)

    def __str__(self) -> str:
        return self.module + (f":{self.name}" if self.name else "")

    def __lt__(self, other: object) -> bool:
        if isinstance(other, QualifiedRule):
            return str(self) < str(other)
        return NotImplemented


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
    Materialized configuration valid for processing a single file.
    """

    path: Path = field(default_factory=Path)
    root: Path = field(default_factory=Path.cwd)

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
    """
    An individual lint error, with an optional replacement and expected diff.
    """

    rule_name: str
    range: CodeRange
    message: str
    node: CSTNode
    replacement: Optional[NodeReplacement]
    diff: str = ""

    @property
    def autofixable(self) -> bool:
        """
        Whether the violation includes a suggested replacement.
        """
        return bool(self.replacement)


@dataclass
class Result:
    """
    A single lint result for a given file and lint rule.
    """

    path: Path
    violation: Optional[LintViolation]
    error: Optional[Tuple[Exception, str]] = None
