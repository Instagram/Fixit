# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import importlib
import inspect
import io
import pkgutil
import tokenize
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Collection,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Type,
    Union,
    cast,
)

import libcst as cst
from libcst import parse_module
from libcst.metadata import MetadataWrapper
from libcst.metadata.type_inference_provider import _sort_by_position

from fixit.common.base import CstContext, CstLintRule, LintRuleT
from fixit.common.comments import CommentInfo
from fixit.common.config import get_context_config, get_lint_config
from fixit.common.ignores import IgnoreInfo
from fixit.common.line_mapping import LineMappingInfo
from fixit.common.pseudo_rule import PseudoContext, PseudoLintRule
from fixit.common.report import BaseLintRuleReport


if TYPE_CHECKING:
    from libcst.metadata.base_provider import ProviderT

LintRuleCollectionT = List[Union[Type[CstLintRule], Type[PseudoLintRule]]]


class DuplicateLintRuleNames(Exception):
    pass


def import_rule_from_package(
    package_name: str, rule_class_name: str
) -> Optional[LintRuleT]:
    # Imports the first rule with matching class name found in specified package.
    rule: Optional[LintRuleT] = None
    package = importlib.import_module(package_name)
    for _loader, name, is_pkg in pkgutil.walk_packages(
        getattr(package, "__path__", None)
    ):
        full_package_or_module_name = package.__name__ + "." + name
        try:
            module = importlib.import_module(full_package_or_module_name)
            rule = getattr(module, rule_class_name, None)
        except ModuleNotFoundError:
            pass
        if is_pkg:
            rule = import_rule_from_package(
                full_package_or_module_name, rule_class_name
            )

        if rule is not None:
            # Stop early if we have found the rule.
            return rule
    return rule


def import_submodules(package: str, recursive: bool = True) -> Dict[str, ModuleType]:
    """ Import all submodules of a module, recursively, including subpackages. """
    package: ModuleType = importlib.import_module(package)
    results = {}
    # pyre-fixme[16]: `ModuleType` has no attribute `__path__`.
    for _loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + "." + name
        try:
            results[full_name] = importlib.import_module(full_name)
        except ModuleNotFoundError:
            pass
        if recursive and is_pkg:
            results.update(import_submodules(full_name))
    return results


def get_distinct_rules_from_package(
    package: str,
    block_list_rules: List[str] = [],
    seen_names: Optional[Set[str]] = None,
) -> Set[Union[Type[CstLintRule], Type[PseudoLintRule]]]:
    # Get rules from the specified package, omitting rules that appear in the block list.
    # Raises error on repeated rule names.
    # Optional parameter `seen_names` accepts set of names that should not occur in this package.
    rules: Set[Union[Type[CstLintRule], Type[PseudoLintRule]]] = set()
    if seen_names is None:
        seen_names: Set[str] = set()
    for _module_name, module in import_submodules(package).items():
        for name in dir(module):
            try:
                obj = getattr(module, name)
                if (
                    obj is not CstLintRule
                    and (
                        issubclass(obj, CstLintRule) or issubclass(obj, PseudoLintRule)
                    )
                    and not inspect.isabstract(obj)
                ):
                    if name in seen_names:
                        raise DuplicateLintRuleNames(
                            f"Lint rule name {name} is duplicated."
                        )
                    # Add all names (even block-listed ones) to the `names` set for duplicate checking.
                    seen_names.add(name)
                    if name not in block_list_rules:
                        rules.add(obj)
            except TypeError:
                continue
    return rules


def get_rules_from_package(package: str) -> LintRuleCollectionT:
    rules: Set[Union[Type[CstLintRule], Type[PseudoLintRule]]] = set()
    for _module_name, module in import_submodules(package).items():
        for name in dir(module):
            try:
                obj = getattr(module, name)
                if obj is CstLintRule or not issubclass(obj, CstLintRule):
                    continue

                if inspect.isabstract(obj):
                    # skip if a CstLintRule subclass has metaclass=ABCMeta
                    continue
                rules.add(obj)
            except TypeError:
                continue
    return list(rules)


def get_rules_from_config() -> LintRuleCollectionT:
    # Get rules from the packages specified in the lint config file, omitting block-listed rules.
    lint_config = get_lint_config()
    rules: Set[Union[Type[CstLintRule], Type[PseudoLintRule]]] = set()
    all_names: Set[str] = set()
    for package in lint_config.packages:
        rules_from_pkg = get_distinct_rules_from_package(
            package, lint_config.block_list_rules, all_names
        )
        rules.update(rules_from_pkg)
    return list(rules)


def get_rules(extra_packages: List[str] = []) -> LintRuleCollectionT:
    # Deprecated. Use get_rules_from_config instead.
    rules: List[Union[Type[CstLintRule], Type[PseudoLintRule]]] = []
    for package in ["fixit.rules"] + extra_packages:
        rules_from_pkg = get_rules_from_package(package)
        rules += list(rules_from_pkg)
    return rules


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
    config: Optional[Mapping[str, Any]] = None,
    rules: LintRuleCollectionT,
    cst_wrapper: Optional[MetadataWrapper] = None,
) -> Collection[BaseLintRuleReport]:
    """
    May raise a SyntaxError, which should be handled by the
    caller.
    """
    if use_ignore_byte_markers and any(
        pattern.encode() in source for pattern in get_lint_config().block_list_patterns
    ):
        return []

    # pre-process these arguments
    config = config if config is not None else get_context_config(file_path)

    tokens = None
    if use_ignore_comments:
        # Don't compute tokens unless we have to, it slows down
        # `scripts.lint.test_rule`.
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
        r for r in rules if not ignore_info or ignore_info.should_evaluate_rule(r)
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
    if cst_rules:
        if cst_wrapper is None:
            cst_wrapper = MetadataWrapper(
                cst.parse_module(source), unsafe_skip_copy=True
            )
        cst_context = CstContext(cst_wrapper, source, file_path, config)
        _visit_cst_rules_with_context(cst_wrapper, cst_rules, cst_context)
        reports.extend(cst_context.reports)
    if pseudo_rules:
        psuedo_context = PseudoContext(file_path, source, tokens, ast_tree)
        for pr_cls in pseudo_rules:
            reports.extend(pr_cls(psuedo_context).lint_file())

    # filter the accumulated errors that should be noqa'ed
    if ignore_info:
        reports = [r for r in reports if not ignore_info.should_ignore_report(r)]

    return reports


@dataclass(frozen=True)
class LintRuleReportsWithAppliedPatches:
    reports: Collection[BaseLintRuleReport]
    patched_source: str


def remove_from_metadata_cache(
    metadata_cache: Mapping["ProviderT", object], line: int
) -> Mapping["ProviderT", object]:
    new_metadata_cache = {}
    for provider, cache in metadata_cache.items():
        if isinstance(cache, dict) and "types" in cache:
            updated_types = []
            for annotation in cache["types"]:
                if annotation["location"]["stop"]["line"] < line:
                    updated_types.append(annotation)
            # Assign even if updated_types is empty, so we don't get a missing cache error later.
            new_metadata_cache[provider] = {
                "types": sorted(updated_types, key=_sort_by_position)
            }
        else:
            # We currently only expect Pyre type data in our metadata cache as of libcst version 0.3.6.
            # TODO: Once other types of cache become available, we will need to deal with them separately.
            new_metadata_cache[provider] = cache
    return new_metadata_cache


def lint_file_and_apply_patches(
    file_path: Path,
    source: bytes,
    *,
    use_ignore_byte_markers: bool = True,
    use_ignore_comments: bool = True,
    config: Optional[Mapping[str, Any]] = None,
    rules: LintRuleCollectionT,
    metadata_cache: Optional[Mapping["ProviderT", object]] = None,
    max_iter: int = 100,
) -> LintRuleReportsWithAppliedPatches:
    """
    Runs `lint_file` in a loop, patching one auto-fixable report on each iteration.

    Applying a single fix at a time prevents the scenario where multiple autofixes
    to combine in a way that results in invalid code.
    """
    # lint_file will fetch this if we don't, but it requires disk I/O, so let's fetch it
    # here to avoid hitting the disk inside our autofixer loop.
    config = config if config is not None else get_context_config(file_path)

    reports = []
    fixed_reports = []
    # Avoid getting stuck in an infinite loop, cap the number of iterations at `max_iter`.
    for i in range(max_iter):
        cst_wrapper = None
        if metadata_cache is not None:
            # Re-compute the cst wrapper on each iteration with the new `source`.
            cst_wrapper = MetadataWrapper(parse_module(source), True, metadata_cache)
        reports = lint_file(
            file_path,
            source,
            use_ignore_byte_markers=use_ignore_byte_markers,
            use_ignore_comments=use_ignore_comments,
            config=config,
            rules=rules,
            cst_wrapper=cst_wrapper,
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
