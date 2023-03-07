# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import functools
import logging
import time
from contextlib import contextmanager
from dataclasses import replace
from typing import (
    Callable,
    ClassVar,
    Collection,
    ContextManager,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Set,
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
    FullRepoManager,
    FullyQualifiedNameProvider,
    MetadataWrapper,
    PositionProvider,
    ProviderT,
)

from fixit.ftypes import Config, FileContent, LintViolation
from . import LintRule, LintRunner, TimingsHook


VisitorMethod = Callable[[CSTNode], None]
VisitHook = Callable[[str], ContextManager]

logger = logging.getLogger(__name__)


class CSTLintRunner(LintRunner["CSTLintRule"]):
    def collect_violations(
        self,
        source: FileContent,
        rules: Collection["CSTLintRule"],
        config: Config,
        timings_hook: Optional[TimingsHook] = None,
    ) -> Iterable[LintViolation]:
        """Run multiple `CSTLintRule`s and yield any lint violations.

        The optional `timings_hook` parameter will be called (if provided) after all
        lint rules have finished running, passing in a dictionary of
        ``RuleName.visit_function_name`` -> ``duration in microseconds``.
        """

        @contextmanager
        def visit_hook(name: str) -> Iterator[None]:
            start = time.perf_counter()
            try:
                yield
            finally:
                duration_us = int(1000 * 1000 * (time.perf_counter() - start))
                logger.debug(f"PERF: {name} took {duration_us} µs")
                self.timings[name] += duration_us

        metadata_cache: Mapping[ProviderT, object] = {}
        needs_repo_manager: Set[ProviderT] = set()

        for rule in rules:
            rule._visit_hook = visit_hook
            for provider in rule.get_inherited_dependencies():
                if provider.gen_cache is not None:
                    # TODO: find a better way to declare this requirement in LibCST
                    needs_repo_manager.add(provider)

        if needs_repo_manager:
            repo_manager = FullRepoManager(
                repo_root_dir=config.root.as_posix(),
                paths=[config.path.as_posix()],
                providers={FullyQualifiedNameProvider},
            )
            repo_manager.resolve_cache()
            metadata_cache = repo_manager.get_cache_for_path(config.path.as_posix())

        mod = MetadataWrapper(
            parse_module(source, path=config.path),
            unsafe_skip_copy=True,
            cache=metadata_cache,
        )
        mod.visit_batched(rules)
        for rule in rules:
            for violation in rule._violations:
                yield violation
        if timings_hook:
            timings_hook(self.timings)


class CSTLintRule(LintRule, BatchableCSTVisitor):
    """Lint rule implemented using LibCST.

    To build a new lint rule, subclass this and `Implement a CST visitor
    <https://libcst.readthedocs.io/en/latest/tutorial.html#Build-Visitor-or-Transformer>`_.
    When a lint rule violation should be reported, use the :meth:`report` method.
    """

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
        """
        Report a lint rule violation.

        If `message` is not provided, ``self.MESSAGE`` will be used as a violation
        message. If neither of them are available, this method raises `ValueError`.

        The optional `position` parameter can override the location where the
        violation is reported. By default, the entire span of `node` is used. If
        `position` is a `CodePosition`, only a single character is marked.

        The optional `replacement` parameter can be used to provide an auto-fix for this
        lint violation. Replacing `node` with `replacement` should make the lint
        violation go away.
        """
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
