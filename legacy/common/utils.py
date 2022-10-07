# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import importlib
import inspect
import json
import pkgutil
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import cast, Dict, List, Optional, Set, Type, Union

import libcst as cst
from libcst._add_slots import add_slots
from libcst.metadata import BaseMetadataProvider, MetadataWrapper, TypeInferenceProvider
from libcst.metadata.type_inference_provider import PyreData

from fixit.common.base import CstLintRule, LintConfig, LintRuleT
from fixit.common.pseudo_rule import PseudoLintRule


def _dedent(src: str) -> str:
    src = re.sub(r"\A\n", "", src)
    return textwrap.dedent(src)


def dedent_with_lstrip(src: str) -> str:
    src = textwrap.dedent(src)
    if src.startswith("\n"):
        return "".join(src[1:])
    return src


def _str_or_any(value: Optional[int]) -> str:
    return "<any>" if value is None else str(value)


class DuplicateLintRuleNameError(Exception):
    pass


class FixtureFileNotFoundError(Exception):
    pass


class LintRuleNotFoundError(Exception):
    pass


LintRuleCollectionT = Set[Union[Type[CstLintRule], Type[PseudoLintRule]]]
DEFAULT_FILENAME: str = "not/a/real/file/path.py"
DEFAULT_CONFIG: LintConfig = LintConfig(
    repo_root=str(
        Path(__file__).parent.parent
    ),  # Set base config repo_root to `fixit` directory for testing.
)


@add_slots
@dataclass(frozen=True)
class ValidTestCase:
    code: str
    filename: str = DEFAULT_FILENAME
    config: LintConfig = DEFAULT_CONFIG


@add_slots
@dataclass(frozen=True)
class InvalidTestCase:
    code: str
    kind: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    expected_replacement: Optional[str] = None
    filename: str = DEFAULT_FILENAME
    config: LintConfig = DEFAULT_CONFIG
    expected_message: Optional[str] = None

    @property
    def expected_str(self) -> str:
        return f"{_str_or_any(self.line)}:{_str_or_any(self.column)}: {self.kind} ..."


def import_submodules(package: str, recursive: bool = True) -> Dict[str, ModuleType]:
    """Import all submodules of a module, recursively, including subpackages."""
    # pyre-fixme[35]: Target cannot be annotated.
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


def import_distinct_rules_from_package(
    package: str,
    block_list_rules: List[str] = [],
    seen_names: Optional[Set[str]] = None,
    allow_list_rules: Optional[List[str]] = None,
) -> LintRuleCollectionT:
    # Import all rules from the specified package, omitting rules that appear in the block list.
    # Raises error on repeated rule names.
    # Optional parameter `seen_names` accepts set of names that should not occur in this package.
    rules: LintRuleCollectionT = set()
    if seen_names is None:
        # pyre-fixme[35]: Target cannot be annotated.
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
                        raise DuplicateLintRuleNameError(
                            f"Lint rule name {name} is duplicated."
                        )
                    # Add all names (even block-listed ones) to the `names` set for duplicate checking.
                    seen_names.add(name)
                    # For backwards compatibility if `allow_list_rules` is missing fall back to all allowed
                    if not allow_list_rules or name in allow_list_rules:
                        if name not in block_list_rules:
                            rules.add(obj)
            except TypeError:
                continue
    return rules


def gen_type_inference_wrapper(code: str, pyre_fixture_path: Path) -> MetadataWrapper:
    # Given test case source code and a path to a pyre fixture file, generate a MetadataWrapper for a lint rule test case.
    module = cst.parse_module(_dedent(code))
    provider_type = TypeInferenceProvider
    try:
        pyre_json_data: PyreData = json.loads(pyre_fixture_path.read_text())
    except FileNotFoundError as e:
        raise FixtureFileNotFoundError(
            f"Fixture file not found at {e.filename}. "
            + "Please run `python -m fixit.common.generate_pyre_fixtures <rule>` to generate fixtures."
        )
    return MetadataWrapper(
        module=module,
        cache={cast(Type[BaseMetadataProvider[object]], provider_type): pyre_json_data},
    )


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


def find_and_import_rule(rule_class_name: str, packages: List[str]) -> LintRuleT:
    for package in packages:
        imported_rule = import_rule_from_package(package, rule_class_name)
        if imported_rule is not None:
            return imported_rule

    # If we get here, the rule was not found.
    raise LintRuleNotFoundError(
        f"Could not find lint rule {rule_class_name} in the following packages: \n"
        + "\n".join(packages)
    )
