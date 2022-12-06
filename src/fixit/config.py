# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import importlib
import inspect
import logging
import pkgutil
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import (
    Any,
    Collection,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Type,
)

from .ftypes import (
    Config,
    is_collection,
    is_sequence,
    QualifiedRule,
    QualifiedRuleRegex,
    RawConfig,
    RuleOptionsTable,
    RuleOptionTypes,
)
from .rule import LintRule
from .rule.cst import CSTLintRule

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

log = logging.getLogger(__name__)


class ConfigError(ValueError):
    def __init__(self, msg: str, config: RawConfig):
        super().__init__(msg)
        self.config = config


def collect_rules(
    enables: Collection[QualifiedRule], disables: Collection[QualifiedRule]
) -> Collection[LintRule]:
    """
    Import and return rules specified by `enables` and `disables`.
    """

    def is_rule(obj: object) -> bool:
        return (
            inspect.isclass(obj)
            and issubclass(obj, LintRule)
            and obj not in (LintRule, CSTLintRule)
        )

    def _collect(rule: QualifiedRule) -> Iterable[Type[LintRule]]:
        try:
            if rule.local:
                # TODO: handle local imports correctly
                return
            else:
                module = importlib.import_module(rule.module)
            module_rules = _walk(module)

            if rule.name:
                if value := module_rules.get(rule.name, None):
                    if issubclass(value, LintRule):
                        yield value
                    elif is_collection(value):
                        for v in value:
                            if issubclass(v, LintRule):
                                yield v
                    else:
                        log.warning("don't know what to do with {value!r}")
                else:
                    log.warning(f"{rule.name!r} not found in {module_rules}")
                    pass  # TODO: error maybe? ¯\_(ツ)_/¯

            else:
                for name in sorted(module_rules.keys()):
                    yield module_rules[name]

        except ImportError:
            log.warning(f"could not import rule(s) {rule}")

    def _walk(module: ModuleType) -> Dict[str, Type[LintRule]]:
        rules: Dict[str, Type[LintRule]] = {}

        members = inspect.getmembers(module, is_rule)
        rules.update(members)

        if hasattr(module, "__path__"):
            for _, module_name, is_pkg in pkgutil.iter_modules(module.__path__):
                if not is_pkg:  # do not recurse to sub-packages
                    mod = importlib.import_module(f".{module_name}", module.__name__)
                    rules.update(_walk(mod))

        return rules

    final_rules: Set[Type[LintRule]] = set()
    for qualified_rule in enables:
        matched_rules = list(_collect(qualified_rule))
        final_rules.update(matched_rules)

    for qualified_rule in disables:
        matched_rules = list(_collect(qualified_rule))
        final_rules.difference_update(matched_rules)

    return [R() for R in final_rules]


def locate_configs(path: Path, root: Optional[Path] = None) -> List[Path]:
    """
    Given a file path, locate all relevant config files in priority order.

    Walking upward from target path, creates a list of candidate paths that exist
    on disk, ordered from nearest/highest priority to further/lowest priority.

    If root is given, only return configs between path and root (inclusive), ignoring
    any paths outside of root, even if they would contain relevant configs.
    If given, root must contain path.

    Returns a list of config paths in priority order, from highest priority to lowest.
    """
    results: List[Path] = []

    if not path.is_dir():
        path = path.parent

    root = root.resolve() if root is not None else Path(path.anchor)
    path.relative_to(root)  # enforce path being inside root

    while True:
        candidates = (
            path / "fixit.toml",
            path / "pyproject.toml",
        )

        for candidate in candidates:
            if candidate.is_file():
                results.append(candidate)

        if path == root or path == path.parent:
            break

        path = path.parent

    return results


def read_configs(paths: List[Path]) -> List[RawConfig]:
    """
    Read config data for each path given, and return their raw toml config values.

    Skips any path with no — or empty — `tool.fixit` section.
    Stops early at any config with `root = true`.

    Maintains the same order as given in paths, minus any skipped files.
    """
    configs: List[RawConfig] = []

    for path in paths:
        path = path.resolve()
        content = path.read_text()
        data = tomllib.loads(content)
        fixit_data = data.get("tool", {}).get("fixit", {})

        if fixit_data:
            config = RawConfig(path=path, data=fixit_data)
            configs.append(config)

            if config.data.get("root", False):
                break

    return configs


def get_sequence(
    config: RawConfig, key: str, *, data: Optional[Dict[str, Any]] = None
) -> Sequence[str]:
    if data:
        value = data.pop(key, ())
    else:
        value = config.data.pop(key, ())

    if not is_sequence(value):
        raise ConfigError(
            f"{key!r} must be array of values, got {type(key)}", config=config
        )

    return value


def get_options(
    config: RawConfig, key: str, *, data: Optional[Dict[str, Any]] = None
) -> RuleOptionsTable:
    if data:
        mapping = data.pop(key, {})
    else:
        mapping = config.data.pop(key, {})

    if not isinstance(mapping, Mapping):
        raise ConfigError(
            f"{key!r} must be mapping of values, got {type(key)}", config=config
        )

    rule_configs: RuleOptionsTable = {}
    for rule_name, rule_config in mapping.items():
        rule_configs[rule_name] = {}
        for key, value in rule_config.items():
            if not isinstance(value, RuleOptionTypes):
                raise ConfigError(
                    f"{key!r} must be one of {RuleOptionTypes}, got {type(value)}",
                    config=config,
                )

            rule_configs[rule_name][key] = value

    return rule_configs


def merge_configs(
    path: Path, raw_configs: List[RawConfig], root: Optional[Path] = None
) -> Config:
    """
    Given multiple raw configs, merge them in priority order.

    Assumes raw_configs are given in order from highest to lowest priority.
    """

    config: RawConfig
    enable_rules: Set[QualifiedRule] = set()
    disable_rules: Set[QualifiedRule] = set()
    rule_options: RuleOptionsTable = {}

    def process_subpath(
        subpath: Path,
        *,
        enable: Sequence[str] = (),
        disable: Sequence[str] = (),
        options: Optional[RuleOptionsTable] = None,
    ):
        subpath = subpath.resolve()
        try:
            path.relative_to(subpath)
        except ValueError:  # not relative to subpath
            return

        for rule in enable:
            if not (match := QualifiedRuleRegex.match(rule)):
                raise ConfigError(f"invalid rule name {rule!r}", config=config)

            group = match.groupdict()
            qual_rule = QualifiedRule(module=group["module"], name=group["name"], local=group["local"])  # type: ignore

            if qual_rule.local:
                qual_rule = replace(qual_rule, root=subpath)

            enable_rules.add(qual_rule)
            disable_rules.discard(qual_rule)

        for rule in disable:
            if not (match := QualifiedRuleRegex.match(rule)):
                raise ConfigError(f"invalid rule name {rule!r}", config=config)

            group = match.groupdict()
            qual_rule = QualifiedRule(module=group["module"], name=group["name"], local=group["local"])  # type: ignore

            enable_rules.discard(qual_rule)
            disable_rules.add(qual_rule)

        if options:
            rule_options.update(options)

    for config in reversed(raw_configs):
        if root is None:
            root = config.path.parent

        data = config.data
        if data.pop("root", False):
            root = config.path.parent

        process_subpath(
            config.path.parent,
            enable=get_sequence(config, "enable"),
            disable=get_sequence(config, "disable"),
            options=get_options(config, "options"),
        )

        for override in get_sequence(config, "overrides"):
            if not isinstance(override, dict):
                raise ConfigError("'overrides' requires array of tables", config=config)

            subpath = override.get("path", None)
            if not subpath:
                raise ConfigError(
                    "'overrides' table requires 'path' value", config=config
                )

            subpath = config.path.parent / subpath
            process_subpath(
                subpath,
                enable=get_sequence(config, "enable", data=override),
                disable=get_sequence(config, "disable", data=override),
                options=get_options(config, "options", data=override),
            )

        for key in data.keys():
            log.warning("unknown configuration option %r", key)

    return Config(
        path=path,
        root=root or Path(path.anchor),
        enable=sorted(enable_rules) or [QualifiedRule("fixit.rules")],
        disable=sorted(disable_rules),
        options=rule_options,
    )


def generate_config(path: Path, root: Optional[Path] = None) -> Config:
    """
    Given a file path, walk upwards looking for and applying cascading configs
    """
    path = path.resolve()

    if root is not None:
        root = root.resolve()

    config_paths = locate_configs(path, root=root)
    raw_configs = read_configs(config_paths)
    return merge_configs(path, raw_configs, root=root)
