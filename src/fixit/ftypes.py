# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import platform
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Collection,
    Container,
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

from libcst import CSTNode, CSTNodeT, FlattenSentinel, RemovalSentinel
from libcst._add_slots import add_slots
from libcst.metadata import CodePosition as CodePosition, CodeRange as CodeRange
from packaging.version import Version

__all__ = ("Version",)

T = TypeVar("T")

STDIN = Path("-")

CodeRange
CodePosition

FileContent = bytes
RuleOptionTypes = (str, int, float)
RuleOptions = Dict[str, Union[str, int, float]]
RuleOptionsTable = Dict[str, RuleOptions]

NodeReplacement = Union[CSTNodeT, FlattenSentinel[CSTNodeT], RemovalSentinel]

Timings = Dict[str, int]
TimingsHook = Callable[[Timings], None]

VisitorMethod = Callable[[CSTNode], None]
VisitHook = Callable[[str], ContextManager[None]]


class OutputFormat(str, Enum):
    custom = "custom"
    fixit = "fixit"
    # json = "json"  # TODO
    vscode = "vscode"


@dataclass(frozen=True)
class Invalid:
    code: str
    range: Optional[CodeRange] = None
    expected_message: Optional[str] = None
    expected_replacement: Optional[str] = None


@dataclass(frozen=True)
class Valid:
    code: str


LintIgnoreRegex = re.compile(
    r"""
    \#\s*                   # leading hash and whitespace
    (lint-(?:ignore|fixme)) # directive
    (?:
        (?::\s*|\s+)        # separator
        (
            \w+             # first rule name
            (?:,\s*\w+)*    # subsequent rule names
        )
    )?                      # rule names are optional
    """,
    re.VERBOSE,
)


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


@dataclass(frozen=True)
class Tags(Container[str]):
    include: Tuple[str, ...] = ()
    exclude: Tuple[str, ...] = ()

    @staticmethod
    def parse(value: Optional[str]) -> "Tags":
        if not value:
            return Tags()

        include = set()
        exclude = set()
        tokens = {value.strip() for value in value.lower().split(",")}
        for token in tokens:
            if token[0] in "!^-":
                exclude.add(token[1:])
            else:
                include.add(token)

        return Tags(
            include=tuple(sorted(include)),
            exclude=tuple(sorted(exclude)),
        )

    def __bool__(self) -> bool:
        return bool(self.include) or bool(self.exclude)

    def __contains__(self, value: object) -> bool:
        tags: Collection[str]

        if isinstance(value, str):
            tags = (value,)
        elif isinstance(value, Collection):
            tags = value
        else:
            return False

        if any(tag in self.exclude for tag in tags):
            return False

        if not self.include or any(tag in self.include for tag in tags):
            return True

        return False


@dataclass
class Options:
    """
    Command-line options to affect runtime behavior
    """

    debug: Optional[bool] = None
    config_file: Optional[Path] = None
    tags: Optional[Tags] = None
    rules: Sequence[QualifiedRule] = ()
    output_format: Optional[OutputFormat] = None
    output_template: str = ""


@dataclass
class LSPOptions:
    """
    Command-line options to affect LSP runtime behavior
    """

    tcp: Optional[int]
    ws: Optional[int]
    stdio: bool = True
    debounce_interval: float = 0.5


@dataclass
class Config:
    """
    Materialized configuration valid for processing a single file.
    """

    path: Path = field(default_factory=Path)
    root: Path = field(default_factory=Path.cwd)

    # feature flags
    enable_root_import: Union[bool, Path] = False

    # rule selection
    enable: List[QualifiedRule] = field(
        default_factory=lambda: [QualifiedRule("fixit.rules")]
    )
    disable: List[QualifiedRule] = field(default_factory=list)
    options: RuleOptionsTable = field(default_factory=dict)

    # filtering criteria
    python_version: Optional[Version] = field(
        default_factory=lambda: Version(platform.python_version())
    )
    tags: Tags = field(default_factory=Tags)

    # post-run processing
    formatter: Optional[str] = None

    # output formatting options
    output_format: OutputFormat = OutputFormat.fixit
    output_template: str = ""

    def __post_init__(self) -> None:
        self.path = self.path.resolve()
        self.root = self.root.resolve()


@dataclass
class RawConfig:
    path: Path
    data: Dict[str, Any]

    def __post_init__(self) -> None:
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
    replacement: Optional[NodeReplacement[CSTNode]]
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
