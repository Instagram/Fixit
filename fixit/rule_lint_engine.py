# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import io
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, List, Optional, Sequence, Type, cast

import libcst as cst
from libcst.metadata import MetadataWrapper

from fixit.common.base import CstContext, CstLintRule, LintConfig
from fixit.common.comments import CommentInfo
from fixit.common.config import get_lint_config
from fixit.common.ignores import IgnoreInfo
from fixit.common.line_mapping import LineMappingInfo
from fixit.common.pseudo_rule import PseudoContext, PseudoLintRule
from fixit.common.report import BaseLintRuleReport
from fixit.common.unused_suppressions import visit_unused_suppressions_rule
from fixit.common.utils import LintRuleCollectionT


def _detect_encoding(source: bytes) -> str:
    return tokenize.detect_encoding(io.BytesIO(source).readline)[0]


def _get_tokens(source: bytes) -> Sequence[tokenize.TokenInfo]:
    return tuple(tokenize.tokenize(io.BytesIO(source).readline))


def _visit_cst_rules_with_context(
    wrapper: MetadataWrapper, rules: Collection[Type[CstLintRule]], context: CstContext
) -> None:
    # construct the rules with the context
    rule_instances = [r(context) for r in rules]
    rule_instances = [r for r in rule_instances if not r.should_skip_file()]

    # before_visit/after_leave are used to update the context
    def before_visit(node: cst.CSTNode) -> None:
        context.node_stack.append(node)

    def after_leave(node: cst.CSTNode) -> None:
        context.node_stack.pop()

    # visit the tree, dispatching to each rule as needed
    wrapper.visit_batched(
        rule_instances, before_visit=before_visit, after_leave=after_leave
    )


def lint_file(
    file_path: Path,
    source: bytes,
    *,
    use_ignore_byte_markers: bool = True,
    use_ignore_comments: bool = True,
    config: Optional[LintConfig] = None,
    rules: LintRuleCollectionT,
    cst_wrapper: Optional[MetadataWrapper] = None,
) -> Collection[BaseLintRuleReport]:
    """
    May raise a SyntaxError, which should be handled by the
    caller.
    """
    # Get settings from the nearest `.fixit.config.yaml` file if necessary.
    config: LintConfig = config if config is not None else get_lint_config()

    if use_ignore_byte_markers and any(
        pattern.encode() in source for pattern in config.block_list_patterns
    ):
        return []

    tokens = None
    if use_ignore_comments:
        # Don't compute tokens unless we have to, it slows down
        # `fixit.cli.run_rules`.
        #
        # `tokenize` is actually much more expensive than generating the whole AST,
        # since AST parsing is heavily optimized C, and tokenize is pure python.
        tokens = _get_tokens(source)
        ignore_info = IgnoreInfo.compute(
            comment_info=CommentInfo.compute(tokens=tokens),
            line_mapping_info=LineMappingInfo.compute(tokens=tokens),
        )
    else:
        ignore_info = None

    # Don't waste time evaluating rules that are globally ignored.
    evaluated_rules = [
        r for r in rules if ignore_info is None or ignore_info.should_evaluate_rule(r)
    ]
    # Categorize lint rules.
    cst_rules: List[Type[CstLintRule]] = []
    pseudo_rules: List[Type[PseudoLintRule]] = []
    for r in evaluated_rules:
        if issubclass(r, CstLintRule):
            cst_rules.append(cast(Type[CstLintRule], r))
        elif issubclass(r, PseudoLintRule):
            pseudo_rules.append(cast(Type[PseudoLintRule], r))

    # `self.context.report()` accumulates reports into the context object, we'll copy
    # those into our local `reports` list.
    ast_tree = None
    reports = []

    if cst_wrapper is None:
        cst_wrapper = MetadataWrapper(cst.parse_module(source), unsafe_skip_copy=True)
    cst_context = CstContext(cst_wrapper, source, file_path, config)
    _visit_cst_rules_with_context(cst_wrapper, cst_rules, cst_context)
    reports.extend(cst_context.reports)

    if pseudo_rules:
        psuedo_context = PseudoContext(file_path, source, tokens, ast_tree)
        for pr_cls in pseudo_rules:
            reports.extend(pr_cls(psuedo_context).lint_file())

    # filter the accumulated errors that should be suppressed and report unused suprressions
    if ignore_info is not None:
        reports = visit_unused_suppressions_rule(
            cst_wrapper, cst_context, reports, ignore_info
        )

    return reports


@dataclass(frozen=True)
class LintRuleReportsWithAppliedPatches:
    reports: Collection[BaseLintRuleReport]
    patched_source: str


def lint_file_and_apply_patches(
    file_path: Path,
    source: bytes,
    *,
    use_ignore_byte_markers: bool = True,
    use_ignore_comments: bool = True,
    config: Optional[LintConfig] = None,
    rules: LintRuleCollectionT,
    max_iter: int = 100,
) -> LintRuleReportsWithAppliedPatches:
    """
    Runs `lint_file` in a loop, patching one auto-fixable report on each iteration.

    Applying a single fix at a time prevents the scenario where multiple autofixes
    to combine in a way that results in invalid code.
    """
    # lint_file will fetch this if we don't, but it requires disk I/O, so let's fetch it
    # here to avoid hitting the disk inside our autofixer loop.
    config = config if config is not None else get_lint_config()

    reports = []
    fixed_reports = []
    # Avoid getting stuck in an infinite loop, cap the number of iterations at `max_iter`.
    for i in range(max_iter):
        reports = lint_file(
            file_path,
            source,
            use_ignore_byte_markers=use_ignore_byte_markers,
            use_ignore_comments=use_ignore_comments,
            config=config,
            rules=rules,
        )

        try:
            first_fixable_report = next(r for r in reports if r.patch is not None)
        except StopIteration:
            # No reports with autofix were found.
            break
        else:
            # We found a fixable report. Patch and re-run the linter on this file.
            patch = first_fixable_report.patch
            assert patch is not None
            # TODO: This is really inefficient because we're forced to decode/reencode
            # the source representation, just so that lint_file can decode the file
            # again.
            #
            # We probably need to rethink how we're representing the source code.
            encoding = _detect_encoding(source)
            source = patch.apply(source.decode(encoding)).encode(encoding)
            fixed_reports.append(first_fixable_report)

    # `reports` shouldn't contain any fixable reports at this point, so there should be
    # no overlap between `fixed_reports` and `reports`.
    return LintRuleReportsWithAppliedPatches(
        reports=(*fixed_reports, *reports), patched_source=source
    )
