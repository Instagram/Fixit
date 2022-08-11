from __future__ import annotations

from typing import ClassVar, Collection, Iterable, List, Set, TypeVar, Type, Generic

from fixit.types import LintViolation, FileContent


class LintRule:
    TAGS: Set[str] = set()
    _violations: List[LintViolation] = []
    _runner: ClassVar[Type[LintRunner]]


SomeRule = TypeVar("SomeRule", bound=LintRule)


class LintRunner(Generic[SomeRule]):
    @classmethod
    def collect_violations(
        cls, source: FileContent, rules: Collection[SomeRule]
    ) -> Iterable[LintViolation]:
        pass


__all__ = ["LintRule", "LintRunner"]
