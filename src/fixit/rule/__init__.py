# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations

from abc import ABC, abstractclassmethod, abstractmethod
from collections import defaultdict

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
)

from fixit.types import FileContent, LintViolation


Timings = Dict[str, int]
TimingsHook = Callable[[Timings], None]


class LintRule(ABC):
    TAGS: Set[str] = set()

    def __init__(self) -> None:
        self._violations: List[LintViolation] = []

    # TODO: this should be an abstract class property
    _runner: ClassVar[Type[LintRunner]]


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


__all__ = ["LintRule", "LintRunner", "Timings", "TimingsHook"]
