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
import yaml
from libcst.metadata import MetadataWrapper

from fixit.common.base import CstContext, CstLintRule
from fixit.common.comments import CommentInfo
from fixit.common.config import BYTE_MARKER_IGNORE_ALL_REGEXP, REPO_ROOT, get_config
from fixit.common.flake8_compat import Flake8PseudoLintRule
from fixit.common.ignores import IgnoreInfo
from fixit.common.line_mapping import LineMappingInfo
from fixit.common.pseudo_rule import PseudoContext, PseudoLintRule
from fixit.common.report import BaseLintRuleReport


LintRuleCollectionT = List[Union[Type[CstLintRule], Type[PseudoLintRule]]]


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


def _find_rules() -> LintRuleCollectionT:
    path = Path(__file__).parent / ".lint.config.yaml"
    if not path.exists():
        raise Exception(f"Missing lint config file: {path}")
    config = yaml.safe_load(path.open())
    if not isinstance(config, dict):
        raise Exception(f"Missing config in lint config file: {path}")
    if "packages" in config and isinstance(config["packages"], list):
        packages: List[str] = config["packages"]
    else:
        raise Exception(f"Missing packages secction in lint config file: {path}")

    rules: Set[Union[Type[CstLintRule], Type[PseudoLintRule]]] = {Flake8PseudoLintRule}
    for package in packages:
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


RULES: LintRuleCollectionT = _find_rules()


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
    file_path: Union[str, Path],
    source: bytes,
    *,
    use_ignore_byte_markers: bool = True,
    use_ignore_comments: bool = True,
    config: Optional[Mapping[str, Any]] = None,
    rules: LintRuleCollectionT = RULES,
) -> Collection[BaseLintRuleReport]:
    """
    May raise a SyntaxError, which should be handled by the
    caller.
    """
    if use_ignore_byte_markers and BYTE_MARKER_IGNORE_ALL_REGEXP.search(source):
        return []

    # pre-process these arguments
    file_path = Path(file_path).resolve().relative_to(REPO_ROOT)
    config = config if config is not None else get_config(file_path)

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
    cst_rules = cast(
        Collection[Type[CstLintRule]],
        [r for r in evaluated_rules if issubclass(r, CstLintRule)],
    )
    pseudo_rules = cast(
        Collection[Type[PseudoLintRule]],
        [r for r in evaluated_rules if issubclass(r, PseudoLintRule)],
    )

    # `self.context.report()` accumulates reports into the context object, we'll copy
    # those into our local `reports` list.
    ast_tree = None
    cst_wrapper = None
    reports = []
    if cst_rules:
        cst_wrapper = MetadataWrapper(cst.parse_module(source), unsafe_skip_copy=True)
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


def lint_file_and_apply_patches(
    file_path: Union[str, Path],
    source: bytes,
    *,
    use_ignore_byte_markers: bool = True,
    use_ignore_comments: bool = True,
    config: Optional[Mapping[str, Any]] = None,
    rules: LintRuleCollectionT = RULES,
) -> LintRuleReportsWithAppliedPatches:
    """
    Runs `lint_file` in a loop, patching the one auto-fixable report on each iteration
    of the loop.

    This is different from how 'arc lint' works. When using 'arc lint', we compute
    minimal-size patches, and hope that they don't overlap. If multiple autofixers
    require overlapping changes, 'arc lint' won't apply them.

    It's also possible for multiple autofixers to combine in a way that results in
    invalid code under `arc lint`. Applying a single fix at a time prevents that.

    There is some risk that the autofixer gets stuck in a loop.

    TODO: Prevent infinite loops by adding a limit to the number of iterations used.
    """
    # lint_file will fetch this if we don't, but it requires disk I/O, so let's fetch it
    # here to avoid hitting the disk inside our autofixer loop.
    config = config if config is not None else get_config(file_path)

    reports = []
    fixed_reports = []
    while True:
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
            # we found no autofixable reports
            break
        else:
            # We found a fixable report. Patch and re-run the linter on this file.
            patch = first_fixable_report.patch
            assert patch is not None  # noqa: IG01
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
