# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Collection, Generator, Iterator, Mapping, Optional, Set

from libcst import CSTNode, CSTTransformer, Module, parse_module
from libcst.metadata import FullRepoManager, MetadataWrapper, ProviderT
from moreorless import unified_diff

from .ftypes import (
    Config,
    FileContent,
    LintViolation,
    NodeReplacement,
    Timings,
    TimingsHook,
)
from .rule import LintRule

LOG = logging.getLogger(__name__)


def diff_violation(path: Path, module: Module, violation: LintViolation) -> str:
    """
    Generate string diff representation of a violation.
    """

    orig = module.code
    mod = module.deep_replace(  # type:ignore # LibCST#906
        violation.node, violation.replacement
    )
    assert isinstance(mod, Module)
    change = mod.code

    return unified_diff(
        orig,
        change,
        path.name,
        n=1,
    )


class LintRunner:
    def __init__(self, path: Path, source: FileContent) -> None:
        self.path = path
        self.source = source
        self.module: Module = parse_module(source)
        self.timings: Timings = defaultdict(lambda: 0)
        self.wrapper = MetadataWrapper(self.module)

    def collect_violations(
        self,
        rules: Collection[LintRule],
        config: Config,
        timings_hook: Optional[TimingsHook] = None,
    ) -> Generator[LintViolation, None, int]:
        """Run multiple `LintRule`s and yield any lint violations.

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
                LOG.debug(f"PERF: {name} took {duration_us} µs")
                self.timings[name] += duration_us

        metadata_cache: Mapping[ProviderT, object] = {}
        self.wrapper = MetadataWrapper(
            self.module, unsafe_skip_copy=True, cache=metadata_cache
        )
        needs_repo_manager: Set[ProviderT] = set()

        for rule in rules:
            rule._visit_hook = visit_hook
            rule._metadata_wrapper = self.wrapper
            for provider in rule.get_inherited_dependencies():
                if provider.gen_cache is not None:
                    # TODO: find a better way to declare this requirement in LibCST
                    needs_repo_manager.add(provider)

        if needs_repo_manager:
            repo_manager = FullRepoManager(
                repo_root_dir=config.root.as_posix(),
                paths=[config.path.as_posix()],
                providers=needs_repo_manager,
            )
            repo_manager.resolve_cache()
            self.wrapper._cache = repo_manager.get_cache_for_path(
                config.path.as_posix()
            )

        self.wrapper.visit_batched(rules)
        count = 0
        for rule in rules:
            for violation in rule._violations:
                count += 1

                if violation.replacement:
                    diff = diff_violation(self.path, self.module, violation)
                    violation = replace(violation, diff=diff)

                yield violation
        if timings_hook:
            timings_hook(self.timings)

        return count

    def apply_replacements(self, violations: Collection[LintViolation]) -> Module:
        """
        Apply any autofixes to the module, and return the resulting source code.
        """
        replacements = {v.node: v.replacement for v in violations if v.replacement}

        class ReplacementTransformer(CSTTransformer):
            def on_visit(self, node: CSTNode) -> bool:
                # don't visit children if we're going to replace the parent anyways
                return node not in replacements

            def on_leave(self, node: CSTNode, updated: CSTNode) -> NodeReplacement:  # type: ignore[type-arg]
                if node in replacements:
                    new = replacements[node]
                    return new
                return updated

        updated: Module = self.module.visit(ReplacementTransformer())
        return updated
