# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import importlib
import inspect
import logging
import pkgutil
import sys
from pathlib import Path
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
)

from .rule import LintRule
from .types import Config, is_sequence, RawConfig, RuleConfigs, RuleConfigTypes

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
    enables: Collection[str], disables: Collection[str]
) -> Collection[LintRule]:
    """
    Import and return rules specified by `enables` and `disables`.
    """

    def _collect(fqname: str) -> Iterable[LintRule]:
        parts = fqname.split(".")
        name = parts.pop(0)
        mod = importlib.import_module(name)
        while parts:
            if hasattr(mod, parts[0]):
                break
            name = f"{name}.{parts.pop(0)}"
            if name in disables:
                log.debug(f"Lint rule discovery for {name} is blocked")
                return
            mod = importlib.import_module(name)

        obj: object = mod
        while parts:
            local_name = parts.pop(0)
            name = f"{name}.{local_name}"
            if name in disables:
                log.debug(f"Lint rule discovery for {name} is blocked")
                return
            obj = getattr(obj, local_name)

        yield from _walk(obj, name)

    def _walk(obj: object, name: str) -> Iterable[LintRule]:
        if inspect.isclass(obj) and issubclass(obj, LintRule):
            if getattr(obj, "__name__", None) in {"CSTLintRule"}:
                # TODO: better way to filter out base classes like CSTLintRule
                return
            log.debug(f"Found lint rule {obj}")
            # mypy can't figure out what's happening here
            yield obj()  # type: ignore
        elif inspect.ismodule(obj) and hasattr(obj, "__path__"):
            for _, local_name, _ in pkgutil.iter_modules(obj.__path__):
                fqname = f"{obj.__name__}.{local_name}"
                if fqname in disables:
                    log.debug("Lint rule discovery for {fqname} is blocked")
                    continue
                yield from _walk(importlib.import_module(fqname), fqname)
        elif inspect.ismodule(obj):
            for local_name, subobj in inspect.getmembers(obj, inspect.isclass):
                fqname = f"{name}.{local_name}"
                if fqname in disables:
                    log.debug(f"Lint rule discovery for {fqname} is blocked")
                    continue
                yield from _walk(subobj, fqname)

    ret: List[LintRule] = []
    for pkg in enables:
        ret.extend(_collect(pkg))
    return ret


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
) -> RuleConfigs:
    if data:
        mapping = data.pop(key, {})
    else:
        mapping = config.data.pop(key, {})

    if not isinstance(mapping, Mapping):
        raise ConfigError(
            f"{key!r} must be mapping of values, got {type(key)}", config=config
        )

    rule_configs: RuleConfigs = {}
    for rule_name, rule_config in mapping.items():
        rule_configs[rule_name] = {}
        for key, value in rule_config.items():
            if not isinstance(value, RuleConfigTypes):
                raise ConfigError(
                    f"{key!r} must be one of {RuleConfigTypes}, got {type(value)}",
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

    enable_rules: Set[str] = set()
    disable_rules: Set[str] = set()
    local_paths: List[Path] = []
    rule_options: RuleConfigs = {}

    def process_subpath(
        subpath: Path,
        *,
        enable: Sequence[str] = (),
        disable: Sequence[str] = (),
        options: Optional[RuleConfigs] = None,
    ):
        subpath = subpath.resolve()
        if not path.is_relative_to(subpath):
            return

        for rule in enable:
            if rule.startswith("."):
                if not local_paths or local_paths[0] != subpath:
                    local_paths.insert(0, subpath)

            enable_rules.add(rule)
            disable_rules.discard(rule)

        for rule in disable:
            enable_rules.discard(rule)
            disable_rules.add(rule)

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
        enable=sorted(enable_rules) or ["fixit.rules"],
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
