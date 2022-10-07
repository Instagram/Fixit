# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

import libcst as cst
from libcst.helpers import get_full_name_for_node_or_raise
from libcst.metadata import GlobalScope, ScopeProvider

from fixit import (
    CstContext,
    CstLintRule,
    InvalidTestCase as Invalid,
    LintConfig,
    ValidTestCase as Valid,
)


TEST_REPO_ROOT: str = str(Path(__file__).parent.parent)


class RuleAction(Enum):
    ALLOW = "allow"  # allow everywhere
    DENY = "deny"  # deny everywhere
    ALLOW_GLOBAL = "allow_global"  # allow in global scope
    ALLOW_LOCAL = "allow_local"  # allow in local scopes
    DENY_GLOBAL = "deny_global"  # deny in global scope
    DENY_LOCAL = "deny_local"  # deny in local scopes


def _gen_testcase_config(dir_rules: Dict[str, object]) -> LintConfig:
    return LintConfig(
        repo_root=TEST_REPO_ROOT, rule_config={"ImportConstraintsRule": dir_rules}
    )


@dataclass(frozen=True)
class _ImportRule:
    pattern: str  # dot-separated module/package name prefix, or wildcard (*)
    action: RuleAction

    @staticmethod
    def from_config(rule: object) -> "_ImportRule":
        if not isinstance(rule, list) or len(rule) != 2:
            raise ValueError(
                f"Invalid entry `{rule}`.\n"
                + "Each rule under a directory must specify a module and an action."
                + ' E.g. \'["*", "deny"]\''
            )
        else:
            module, action = rule
            return _ImportRule(module, RuleAction(action))

    @property
    def is_wildcard(self) -> bool:
        return self.pattern == "*"

    def match(self, global_name: str) -> bool:
        if self.is_wildcard:
            return True

        split_pattern = self.pattern.split(".")
        return global_name.split(".")[: len(split_pattern)] == split_pattern


@dataclass(frozen=True)
class _ImportConfig:
    rules: Sequence[_ImportRule]
    ignore_tests: bool
    ignore_types: bool
    message: Optional[str]

    @staticmethod
    def from_config(settings_for_dir: Dict[object, object]) -> "_ImportConfig":
        rule_settings_for_dir = settings_for_dir.get("rules", [])

        if not isinstance(rule_settings_for_dir, list):
            raise ValueError(
                f"Invalid entry `{rule_settings_for_dir}`.\n"
                + "The `rules` setting must be a list of rules."
            )

        rules_for_file = []
        for rule in rule_settings_for_dir:
            rules_for_file.append(_ImportRule.from_config(rule))

        ignore_tests = settings_for_dir.get("ignore_tests", True)
        ignore_types = settings_for_dir.get("ignore_types", True)
        message = settings_for_dir.get("message")
        if not isinstance(ignore_tests, bool):
            raise ValueError("Setting `ignore_tests` value must be 'True' or 'False'.")
        if not isinstance(ignore_types, bool):
            raise ValueError("Setting `ignore_types` value must be 'True' or 'False'.")
        if message is not None and not isinstance(message, str):
            raise ValueError("Setting `message` value must be a string.")

        return _ImportConfig(
            rules_for_file, ignore_tests, ignore_types, message
        )._validate()

    def _validate(self) -> "_ImportConfig":
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


class ImportConstraintsRule(CstLintRule):
    """
    Rule to impose import constraints in certain directories to improve runtime performance.
    The directories specified in the ImportConstraintsRule setting in the ``.fixit.config.yaml`` file's
    ``rule_config`` section can impose import constraints for that directory and its children as follows::

        rule_config:
            ImportConstraintsRule:
                dir_under_repo_root:
                    rules: [
                        ["module_under_repo_root", "allow"],
                        ["another_module_under_repo_root, "deny"],
                        ["*", "deny"]
                    ]
                    ignore_tests: True
                    ignore_types: True
                    message: "'{imported}' cannot be imported from within '{current_file}'."

    Each rule under ``rules`` is evaluated in order from top to bottom and the last rule for each directory
    should be a wildcard rule. Rules can be ``"allow"``, ``"deny"``, ``"allow_global"``, ``"allow_local"``,
    ``"deny_global"`` or ``"deny_local"``.
    ``ignore_tests`` and `ignore_types` should carry boolean values and can be omitted. They are both set to
    `True` by default.
    If ``ignore_types`` is True, this rule will ignore imports inside ``if TYPE_CHECKING`` blocks since those
    imports do not have an affect on runtime performance.
    If ``ignore_tests`` is True, this rule will not lint any files found in a testing module.
    If ``message`` is passed, it must be a string containing a custom message. The string will be formatted
    passing ``imported`` and ``current_file`` variables to be used if needed, with the symbol being imported
    and the current file, respectively.
    """

    _config: Optional[_ImportConfig]
    _repo_root: Path
    _type_checking_stack: List[cst.If]
    _abs_file_path: Path

    METADATA_DEPENDENCIES = (ScopeProvider,)
    MESSAGE: str = (
        "According to the settings for this directory in the .fixit.config.yaml configuration file, "
        + "'{imported}' cannot be imported from within '{current_file}'."
    )

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
        # Deny global
        Valid(
            """
            def local_scope():
                import common
            """,
            config=_gen_testcase_config({"dir": {"rules": [["*", "deny_global"]]}}),
            filename="dir/file.py",
        ),
        # Deny local
        Valid(
            """
            import common
            """,
            config=_gen_testcase_config({"dir": {"rules": [["*", "deny_local"]]}}),
            filename="dir/file.py",
        ),
        # Allow global
        Valid(
            """
            import common
            """,
            config=_gen_testcase_config({"dir": {"rules": [["*", "allow_global"]]}}),
            filename="dir/file.py",
        ),
        # Allow local
        Valid(
            """
            def local_scope():
                import common
            """,
            config=_gen_testcase_config({"dir": {"rules": [["*", "allow_local"]]}}),
            filename="dir/file.py",
        ),
    ]

    INVALID = [
        # Everything is denied
        Invalid(
            "import common",
            config=_gen_testcase_config({"some_dir": {"rules": [["*", "deny"]]}}),
            filename="some_dir/file.py",
        ),
        # Glob for a specific filename
        Invalid(
            "import common",
            config=_gen_testcase_config({"*/file.py": {"rules": [["*", "deny"]]}}),
            filename="some_dir/file.py",
        ),
        # Validate rules are evaluated in order
        Invalid(
            "from common.foo import bar",
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
            config=_gen_testcase_config(
                {"some_dir": {"rules": [["common", "deny"], ["*", "allow"]]}}
            ),
            filename="some_dir/file.py",
        ),
        Invalid(
            "from common import bar as not_bar",
            config=_gen_testcase_config(
                {"some_dir": {"rules": [["common.bar", "deny"], ["*", "allow"]]}}
            ),
            filename="some_dir/file.py",
        ),
        # Relative imports
        Invalid(
            "from . import b",
            config=_gen_testcase_config({"common": {"rules": [["*", "deny"]]}}),
            filename="common/a.py",
        ),
        # File belongs to more than one directory setting, import from
        Invalid(
            "from common.foo import bar",
            config=_gen_testcase_config(
                {
                    "dir_1/dir_2": {"rules": [["*", "deny"]]},
                    "dir_1": {
                        "rules": [["common.foo.bar", "allow"], ["*", "deny"]],
                    },
                }
            ),
            filename="dir_1/dir_2/file.py",
        ),
        # File belongs to more than one directory setting, import
        Invalid(
            "import common",
            config=_gen_testcase_config(
                {
                    "dir_1/dir_2": {"rules": [["*", "deny"]]},
                    "dir_1": {
                        "rules": [["common", "allow"], ["*", "deny"]],
                    },
                }
            ),
            filename="dir_1/dir_2/file.py",
        ),
        # Deny global
        Invalid(
            """
            import common
            """,
            config=_gen_testcase_config({"dir": {"rules": [["*", "deny_global"]]}}),
            filename="dir/file.py",
        ),
        # Deny local
        Invalid(
            """
            def local_scope():
                import common
            """,
            config=_gen_testcase_config({"dir": {"rules": [["*", "deny_local"]]}}),
            filename="dir/file.py",
        ),
        # Allow global
        Invalid(
            """
            def local_scope():
                import common
            """,
            config=_gen_testcase_config({"dir": {"rules": [["*", "allow_global"]]}}),
            filename="dir/file.py",
        ),
        # Allow local
        Invalid(
            """
            import common
            """,
            config=_gen_testcase_config({"dir": {"rules": [["*", "allow_local"]]}}),
            filename="dir/file.py",
        ),
        # Custom message
        Invalid(
            """
            import common
            """,
            config=_gen_testcase_config(
                {
                    "dir": {
                        "rules": [["*", "deny"]],
                        "message": "'{imported}' cannot be imported from '{current_file}'",
                    }
                }
            ),
            filename="dir/file.py",
            expected_message=f"'common' cannot be imported from 'dir{os.path.sep}file.py'",
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
        if import_constraints_config is not None:
            formatted_config: Dict[
                Path, Dict[object, object]
            ] = self._parse_and_format_config(import_constraints_config)
            # Try matching the filepath and all of its parents paths in any of the
            # given configurations' glob patterns, stopping early if a match is
            # found in the config. The closest match in the settings will be used.
            parts = list(self._abs_file_path.parts)
            while parts:
                part_dir = os.path.join(*parts)
                parts.pop()
                for pattern, settings_for_dir in formatted_config.items():
                    if fnmatch(part_dir, str(pattern)):
                        self._config = _ImportConfig.from_config(settings_for_dir)
                        break
                if self._config is not None:
                    break
        self._type_checking_stack = []

    def _parse_and_format_config(
        self, import_constraints_config: Dict[str, object]
    ) -> Dict[Path, Dict[object, object]]:
        # Normalizes paths, and converts all paths to absolute paths using the specified repo_root.
        formatted_config: Dict[Path, Dict[object, object]] = {}
        for dirname, dir_settings in import_constraints_config.items():
            abs_dirpath: Optional[Path] = None

            # If it's an absolute path, make sure it's relative to repo_root (which should be an absolute path).
            if os.path.isabs(dirname):
                if dirname.startswith(str(self._repo_root)):
                    abs_dirpath = Path(dirname)
            # Otherwise assume all relative paths exist under repo_root, and don't add paths that leave repo_root (eg: '../path')
            else:
                abs_dirname = os.path.normpath(os.path.join(self._repo_root, dirname))
                if abs_dirname.startswith(str(self._repo_root)):
                    abs_dirpath = Path(abs_dirname)

            if not isinstance(dir_settings, dict):
                raise ValueError(
                    f"Invalid entry `{dir_settings}`.\n"
                    + "You must specify settings in key-value format under a directory."
                )
            if abs_dirpath is not None:
                formatted_config[abs_dirpath] = dir_settings

        return formatted_config

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
        message = config.message or self.MESSAGE
        for name in names:
            if name.split(".", 1)[0] not in _get_local_roots(self._repo_root):
                continue
            rule = config.match(name)
            action = rule.action
            if action in {
                RuleAction.ALLOW_GLOBAL,
                RuleAction.ALLOW_LOCAL,
                RuleAction.DENY_GLOBAL,
                RuleAction.DENY_LOCAL,
            }:
                scope = self.get_metadata(ScopeProvider, node)
                if isinstance(scope, GlobalScope):
                    if action in {RuleAction.ALLOW_GLOBAL, RuleAction.DENY_LOCAL}:
                        continue
                else:
                    if action in {RuleAction.ALLOW_LOCAL, RuleAction.DENY_GLOBAL}:
                        continue
            elif action == RuleAction.ALLOW:
                continue
            self.report(
                node,
                message.format(
                    imported=name,
                    current_file=self.context.file_path,
                ),
            )
