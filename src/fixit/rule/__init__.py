# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict

from dataclasses import dataclass

from typing import (
    Callable,
    ClassVar,
    Collection,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

from fixit.ftypes import CodeRange, FileContent, LintViolation


Timings = Dict[str, int]
TimingsHook = Callable[[Timings], None]


@dataclass(frozen=True)
class InvalidTestCase:
    code: str
    range: Optional[CodeRange] = None
    expected_message: Optional[str] = None
    expected_replacement: Optional[str] = None


@dataclass(frozen=True)
class ValidTestCase:
    code: str


class LintRule(ABC):  # noqa: B024
    TAGS: Set[str] = set()

    def __init__(self) -> None:
        self._violations: List[LintViolation] = []

    # TODO: these should be an abstract class property
    _runner: ClassVar[Type[LintRunner]]

    VALID: ClassVar[List[Union[str, ValidTestCase]]]
    INVALID: ClassVar[List[Union[str, InvalidTestCase]]]


SomeRule = TypeVar("SomeRule", bound=LintRule)


class LintRunner(ABC, Generic[SomeRule]):
    def __init__(self) -> None:
        self.timings: Timings = defaultdict(lambda: 0)

    @abstractmethod
    def collect_violations(
        self,
        source: FileContent,
        rules: Collection[SomeRule],
        timings_hook: Optional[TimingsHook] = None,
    ) -> Iterable[LintViolation]:
        pass


__all__ = [
    "LintRule",
    "LintRunner",
    "Timings",
    "TimingsHook",
    "InvalidTestCase",
    "ValidTestCase",
]
