import functools
import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import replace
from typing import (
    Callable,
    ClassVar,
    Collection,
    ContextManager,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Set,
    TypeVar,
    Union,
)

from libcst import (
    BatchableCSTVisitor,
    CSTNode,
    FlattenSentinel,
    parse_module,
    RemovalSentinel,
)
from libcst.metadata import (
    CodePosition,
    CodeRange,
    MetadataWrapper,
    PositionProvider,
    ProviderT,
)

from fixit.types import FileContent, LintViolation
from . import LintRule, LintRunner, TimingsHook


VisitorMethod = Callable[[CSTNode], None]
VisitHook = Callable[[str], ContextManager]

logger = logging.getLogger(__name__)


class CSTLintRunner(LintRunner["CSTLintRule"]):
    def collect_violations(
        self,
        source: FileContent,
        rules: Collection["CSTLintRule"],
        timings_hook: Optional[TimingsHook] = None,
    ) -> Iterable[LintViolation]:
        @contextmanager
        def visit_hook(name: str) -> Iterator[None]:
            start = time.perf_counter()
            try:
                yield
            finally:
                duration_us = int(1000 * 1000 * (time.perf_counter() - start))
                logger.debug(f"PERF: {name} took {duration_us} µs")
                self.timings[name] += duration_us

        for rule in rules:
            rule._visit_hook = visit_hook

        mod = MetadataWrapper(parse_module(source), unsafe_skip_copy=True)
        mod.visit_batched(rules)
        for rule in rules:
            for violation in rule._violations:
                yield violation
        if timings_hook:
            timings_hook(self.timings)


class CSTLintRule(LintRule, BatchableCSTVisitor):
    METADATA_DEPENDENCIES: ClassVar[Collection[ProviderT]] = (PositionProvider,)

    _runner = CSTLintRunner
    _visit_hook: Optional[VisitHook] = None

    def report(
        self,
        node: CSTNode,
        message: Optional[str] = None,
        *,
        position: Optional[Union[CodePosition, CodeRange]] = None,
        replacement: Optional[Union[CSTNode, RemovalSentinel, FlattenSentinel]] = None,
    ) -> None:
        rule_name = type(self).__name__
        if not message:
            # backwards compat with Fixit 1.0 api
            message = getattr(self, "MESSAGE", None)
            if not message:
                raise ValueError(f"No message provided in {rule_name}")

        if position is None:
            position = self.get_metadata(PositionProvider, node)
        elif isinstance(position, CodePosition):
            end = replace(position, line=position.line + 1, column=0)
            position = CodeRange(start=position, end=end)
        self._violations.append(
            LintViolation(
                rule_name,
                range=position,
                message=message,
                autofixable=bool(replacement),
            )
        )

    def get_visitors(self) -> Mapping[str, VisitorMethod]:
        def _wrap(name: str, func: VisitorMethod) -> VisitorMethod:
            @functools.wraps(func)
            def wrapper(node: CSTNode) -> None:
                if self._visit_hook:
                    with self._visit_hook(name):
                        return func(node)
                return func(node)

            return wrapper

        return {
            name: _wrap(f"{type(self).__name__}.{name}", visitor)
            for (name, visitor) in super().get_visitors().items()
        }


CstLintRule = CSTLintRule
