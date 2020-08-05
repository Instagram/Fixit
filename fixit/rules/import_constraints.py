# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Set

import libcst as cst
from libcst.helpers import get_full_name_for_node_or_raise

from fixit.common.base import CstContext, CstLintRule
from fixit.common.config import get_lint_config
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


IG69_IMPORT_CONSTRAINT_VIOLATION: str = (
    "IG69 According to the .fixit.config.yaml configuration file for this directory, "
    + "{imported} cannot be imported from within {current_file}. "
)


@dataclass(frozen=True)
class _ImportRule:
    pattern: str  # dot-separated module/package name prefix, or wildcard (*)
    allow: bool

    @staticmethod
    def from_config(rule: Sequence[str]) -> "_ImportRule":
        if rule[1] == "allow":
            allow = True
        elif rule[1] == "deny":
            allow = False
        else:
            raise ValueError("rule should either allow or deny a pattern")
        return _ImportRule(rule[0], allow)

    @property
    def is_wildcard(self) -> bool:
        return self.pattern == "*"

    def match(self, global_name: str) -> bool:
        if self.is_wildcard:
            return True

        split_pattern = self.pattern.split(".")
        return global_name.split(".")[: len(split_pattern)] == split_pattern


@dataclass(frozen=True)
class ImportConfig:
    rules: Sequence[_ImportRule]
    ignore_tests: bool
    ignore_types: bool

    @staticmethod
    def from_config(config: Mapping[str, Any]) -> "ImportConfig":
        rules = [_ImportRule.from_config(r) for r in config.get("rules", [])]
        ignore_tests = config.get("ignore_tests", True)
        ignore_types = config.get("ignore_types", True)
        return ImportConfig(rules, ignore_tests, ignore_types)._validate()

    def _validate(self) -> "ImportConfig":
        if len(self.rules) == 0:
            raise ValueError("Must have at least one rule")
        if not self.rules[-1].is_wildcard:
            raise ValueError("The last rule must be a wildcard rule")
        if any(r.is_wildcard for r in self.rules[:-1]):
            raise ValueError("Only the last rule can be a wildcard rule")
        return self

    def match(self, global_name: str) -> "_ImportRule":
        for r in self.rules:
            if r.match(global_name):
                return r
        raise AssertionError(
            "No matching rule was found. The wildcard rule should make this impossible."
        )


@lru_cache(maxsize=None)
def _get_local_roots() -> Set[str]:
    repo_root = get_lint_config().repo_root
    return set(os.listdir(repo_root))


class ImportConstraintsRule(CstLintRule):
    ONCALL_SHORTNAME = "instagram_server_framework"
    _config: Optional[ImportConfig]
    _type_checking_stack: List[cst.If]

    VALID = [
        # Everything is allowed
        Valid("import fixit"),
        Valid("import fixit", config={"rules": [["*", "allow"]]}),
        # This import is allowlisted
        Valid("import fixit", config={"rules": [["fixit", "allow"], ["*", "deny"]]},),
        # Allow children of a allowlisted module
        Valid(
            "from fixit.foo import bar",
            config={"rules": [["fixit", "allow"], ["*", "deny"]]},
        ),
        # Validate rules are evaluted in order
        Valid(
            "from fixit.foo import bar",
            config={
                "rules": [["fixit.foo.bar", "allow"], ["fixit", "deny"], ["*", "deny"],]
            },
        ),
        # Built-in modules are fine
        Valid("import ast", config={"rules": [["*", "deny"]]}),
        # Relative imports
        Valid(
            "from . import module",
            config={"rules": [["fixit.safe", "allow"], ["*", "deny"]]},
            filename="fixit/safe/file.py",
        ),
        Valid(
            "from ..safe import module",
            config={"rules": [["fixit.safe", "allow"], ["*", "deny"]]},
            filename="fixit/unsafe/file.py",
        ),
        # Ignore some relative module that leaves the repo root
        Valid(
            "from ....................................... import module",
            config={"rules": [["*", "deny"]]},
            filename="fixit/file.py",
        ),
    ]

    INVALID = [
        # Everything is denied
        Invalid("import fixit", "IG69", config={"rules": [["*", "deny"]]}),
        # Validate rules are evaluated in order
        Invalid(
            "from fixit.foo import bar",
            "IG69",
            config={
                "rules": [
                    ["fixit.foo.bar", "deny"],
                    ["fixit", "allow"],
                    ["*", "allow"],
                ]
            },
        ),
        # We should match against the real name, not the aliased name
        Invalid(
            "import fixit as not_fixit",
            "IG69",
            config={"rules": [["fixit", "deny"], ["*", "allow"]]},
        ),
        Invalid(
            "from fixit import bar as not_bar",
            "IG69",
            config={"rules": [["fixit.bar", "deny"], ["*", "allow"]]},
        ),
        # Relative imports
        Invalid(
            "from . import b",
            "IG69",
            config={"rules": [["*", "deny"]]},
            filename="fixit/a.py",
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        rule_config = context.config.get(self.__class__.__name__, None)
        # Check if not None and not an empty dict.
        if rule_config is not None and rule_config:
            self._config = ImportConfig.from_config(rule_config)
        else:
            self._config = None
        self._type_checking_stack = []

    def should_skip_file(self) -> bool:
        config = self._config
        return config is None or (config.ignore_tests and self.context.in_tests)

    def visit_If(self, node: cst.If) -> None:
        # TODO: Handle stuff like typing.TYPE_CHECKING
        test = node.test
        if isinstance(test, cst.Name) and test.value == "TYPE_CHECKING":
            self._type_checking_stack.append(node)

    def leave_If(self, original_node: cst.If) -> None:
        if self._type_checking_stack and self._type_checking_stack[-1] is original_node:
            self._type_checking_stack.pop()

    def visit_Import(self, node: cst.Import) -> None:
        self._check_names(
            node, (get_full_name_for_node_or_raise(alias.name) for alias in node.names)
        )

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        module = node.module
        abs_module = self._to_absolute_module(
            get_full_name_for_node_or_raise(module) if module is not None else "",
            len(node.relative),
        )
        if abs_module is not None:
            names = node.names
            if isinstance(names, Sequence):
                self._check_names(
                    node, (f"{abs_module}.{alias.name.value}" for alias in names)
                )

    def _to_absolute_module(self, module: Optional[str], level: int) -> Optional[str]:
        if level == 0:
            return module

        repo_root = Path(get_lint_config().repo_root)
        # Get the absolute path of the file
        current_dir = repo_root / self.context.file_path
        for __ in range(level):
            current_dir = current_dir.parent

        if current_dir != repo_root and repo_root not in current_dir.parents:
            return None

        prefix = ".".join(current_dir.relative_to(repo_root).parts)
        return f"{prefix}.{module}" if module is not None else prefix

    def _check_names(self, node: cst.CSTNode, names: Iterable[str]) -> None:
        config = self._config
        if config is None or (config.ignore_types and self._type_checking_stack):
            return
        for name in names:
            if name.split(".", 1)[0] not in _get_local_roots():
                continue
            rule = config.match(name)
            if not rule.allow:
                self.report(
                    node,
                    IG69_IMPORT_CONSTRAINT_VIOLATION.format(
                        imported=name, current_file=self.context.file_path
                    ),
                )
