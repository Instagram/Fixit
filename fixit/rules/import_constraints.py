# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set

import libcst as cst
from libcst.helpers import get_full_name_for_node_or_raise

from fixit.common.base import CstContext, CstLintRule, LintConfig
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


IG69_IMPORT_CONSTRAINT_VIOLATION: str = (
    "IG69 According to the .fixit.config.yaml configuration file for this directory, "
    + "{imported} cannot be imported from within {current_file}. "
)


TEST_REPO_ROOT: str = str(Path(__file__).parent.parent)


def _gen_testcase_config(dir_rules: Dict[str, object]) -> LintConfig:
    return LintConfig(
        repo_root=TEST_REPO_ROOT, rule_config={"ImportConstraintsRule": dir_rules}
    )


@dataclass(frozen=True)
class _ImportRule:
    pattern: str  # dot-separated module/package name prefix, or wildcard (*)
    allow: bool

    @staticmethod
    def from_config(module: str, action: str) -> "_ImportRule":
        if action not in ("allow", "deny"):
            raise ValueError("rule should either allow or deny a pattern")
        return _ImportRule(module, action == "allow")

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
def _get_local_roots(repo_root: Path) -> Set[str]:
    return set(os.listdir(repo_root))


@lru_cache()
def _get_formatted_dirnames(
    repo_root: Path, dirnames: FrozenSet[str]
) -> Dict[str, str]:
    formatted_dirnames = {}
    for original_dir in dirnames:
        # If it's an absolute path, get relative to repo_root (which should be an absolute path).
        if os.path.isabs(original_dir):
            # We only want directories that are under repo root.
            if original_dir.startswith(str(repo_root)):
                formatted_relpath = os.path.relpath(original_dir, repo_root)
                formatted_dirnames[formatted_relpath] = original_dir
        # Otherwise assume all relative paths are relative to repo_root.
        else:
            formatted_dirnames[os.path.normpath(original_dir)] = original_dir
    return formatted_dirnames


class ImportConstraintsRule(CstLintRule):
    _config: Optional[ImportConfig]
    _repo_root: Path
    _type_checking_stack: List[cst.If]
    _abs_file_path: Path

    VALID = [
        # Everything is allowed
        Valid("import common"),
        Valid(
            "import common",
            config=_gen_testcase_config({"some_dir": {"rules": [["*", "allow"]]}}),
            filename="some_dir/file.py",
        ),
        # This import is allowlisted
        Valid(
            "import common",
            config=_gen_testcase_config(
                {"some_dir": {"rules": [["common", "allow"], ["*", "deny"]]}}
            ),
            filename="some_dir/file.py",
        ),
        # Allow children of a allowlisted module
        Valid(
            "from common.foo import bar",
            config=_gen_testcase_config(
                {"some_dir": {"rules": [["common", "allow"], ["*", "deny"]]}}
            ),
            filename="some_dir/file.py",
        ),
        # Validate rules are evaluted in order
        Valid(
            "from common.foo import bar",
            config=_gen_testcase_config(
                {
                    "some_dir": {
                        "rules": [
                            ["common.foo.bar", "allow"],
                            ["common", "deny"],
                            ["*", "deny"],
                        ]
                    }
                }
            ),
            filename="some_dir/file.py",
        ),
        # Built-in modules are fine
        Valid(
            "import ast",
            config=_gen_testcase_config({"some_dir": {"rules": [["*", "deny"]]}}),
            filename="some_dir/file.py",
        ),
        # Relative imports
        Valid(
            "from . import module",
            config=_gen_testcase_config(
                {".": {"rules": [["common.safe", "allow"], ["*", "deny"]]}}
            ),
            filename="common/safe/file.py",
        ),
        Valid(
            "from ..safe import module",
            config=_gen_testcase_config(
                {"common": {"rules": [["common.safe", "allow"], ["*", "deny"]]}}
            ),
            filename="common/unsafe/file.py",
        ),
        # Ignore some relative module that leaves the repo root
        Valid(
            "from ....................................... import module",
            config=_gen_testcase_config({".": {"rules": [["*", "deny"]]}}),
            filename="file.py",
        ),
        # File belongs to more than one directory setting (should enforce closest parent directory)
        Valid(
            "from common.foo import bar",
            config=_gen_testcase_config(
                {
                    "dir_1/dir_2": {
                        "rules": [["common.foo.bar", "allow"], ["*", "deny"]]
                    },
                    "dir_1": {"rules": [["common.foo.bar", "deny"], ["*", "deny"]]},
                }
            ),
            filename="dir_1/dir_2/file.py",
        ),
        # File belongs to more than one directory setting, flipped order (should enforce closest parent directory)
        Valid(
            "from common.foo import bar",
            config=_gen_testcase_config(
                {
                    "dir_1": {"rules": [["common.foo.bar", "deny"], ["*", "deny"]]},
                    "dir_1/dir_2": {
                        "rules": [["common.foo.bar", "allow"], ["*", "deny"]]
                    },
                }
            ),
            filename="dir_1/dir_2/file.py",
        ),
    ]

    INVALID = [
        # Everything is denied
        Invalid(
            "import common",
            "IG69",
            config=_gen_testcase_config({"some_dir": {"rules": [["*", "deny"]]}}),
            filename="some_dir/file.py",
        ),
        # Validate rules are evaluated in order
        Invalid(
            "from common.foo import bar",
            "IG69",
            config=_gen_testcase_config(
                {
                    "some_dir": {
                        "rules": [
                            ["common.foo.bar", "deny"],
                            ["common", "allow"],
                            ["*", "allow"],
                        ]
                    }
                }
            ),
            filename="some_dir/file.py",
        ),
        # We should match against the real name, not the aliased name
        Invalid(
            "import common as not_common",
            "IG69",
            config=_gen_testcase_config(
                {"some_dir": {"rules": [["common", "deny"], ["*", "allow"]]}}
            ),
            filename="some_dir/file.py",
        ),
        Invalid(
            "from common import bar as not_bar",
            "IG69",
            config=_gen_testcase_config(
                {"some_dir": {"rules": [["common.bar", "deny"], ["*", "allow"]]}}
            ),
            filename="some_dir/file.py",
        ),
        # Relative imports
        Invalid(
            "from . import b",
            "IG69",
            config=_gen_testcase_config({"common": {"rules": [["*", "deny"]]}}),
            filename="common/a.py",
        ),
        # File belongs to more than one directory setting
        Invalid(
            "from common.foo import bar",
            "IG69",
            config=_gen_testcase_config(
                {
                    "dir_1/dir_2": {"rules": [["common.foo.bar", "deny"]]},
                    "dir_1": {"rules": [["common.foo.bar", "allow"], ["*", "deny"]],},
                }
            ),
            filename="dir_1/dir_2/file.py",
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        self._repo_root = Path(self.context.config.repo_root).resolve()
        self._config = None
        self._abs_file_path = (self._repo_root / context.file_path).resolve()
        import_constraints_config = self.context.config.rule_config.get(
            self.__class__.__name__, None
        )
        # Check if not None and not an empty dict.
        if import_constraints_config is not None:
            rules_for_file = {}
            ignore_tests = True
            ignore_types = True

            formatted_dirnames = _get_formatted_dirnames(
                self._repo_root, frozenset(import_constraints_config.keys())
            )

            # Run through logical ancestors of the filepath in reverse order so that
            # the closest ancestor settings override those from distant ancestors.
            for parent_dir in reversed(self._abs_file_path.parents):
                rel_parent_dir = os.path.relpath(parent_dir, self._repo_root)
                if rel_parent_dir in formatted_dirnames:
                    original_dirname = formatted_dirnames[rel_parent_dir]
                    settings_for_dir = import_constraints_config[original_dirname]
                    if not isinstance(settings_for_dir, dict):
                        raise ValueError(
                            f"Invalid entry `{settings_for_dir}`.\n"
                            + "Each directory must specify key-value pairs of settings."
                        )
                    for rule in settings_for_dir.get("rules", []):
                        try:
                            module, action = rule
                        except ValueError:
                            raise ValueError(
                                f"Invalid entry `{rule}`.\n"
                                + "Each rule under a directory must specify a module and an action."
                                + ' E.g. \'["*", "deny"]\''
                            )
                        rules_for_file[module] = action
                    ignore_tests = settings_for_dir.get("ignore_tests", ignore_tests)
                    ignore_types = settings_for_dir.get("ignore_types", ignore_types)

            if rules_for_file:
                rules = [
                    _ImportRule.from_config(m, action)
                    for m, action in rules_for_file.items()
                ]

                self._config = ImportConfig(
                    rules, ignore_tests, ignore_types
                )._validate()
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

        # Get the absolute path of the file
        current_dir = self._abs_file_path
        for __ in range(level):
            current_dir = current_dir.parent

        if (
            current_dir != self._repo_root
            and self._repo_root not in current_dir.parents
        ):
            return None

        prefix = ".".join(current_dir.relative_to(self._repo_root).parts)
        return f"{prefix}.{module}" if module is not None else prefix

    def _check_names(self, node: cst.CSTNode, names: Iterable[str]) -> None:
        config = self._config
        if config is None or (config.ignore_types and self._type_checking_stack):
            return
        for name in names:
            if name.split(".", 1)[0] not in _get_local_roots(self._repo_root):
                continue
            rule = config.match(name)
            if not rule.allow:
                self.report(
                    node,
                    IG69_IMPORT_CONSTRAINT_VIOLATION.format(
                        imported=name, current_file=self.context.file_path
                    ),
                )
