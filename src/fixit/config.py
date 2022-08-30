# Copyright (c) Meta Platforms, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Collection, Iterable, List, Optional

from fixit.rule import LintRule

from .types import Config, RawConfig

try:
    import tomllib
except ImportError:
    import tomli as tomllib

log = logging.getLogger(__name__)


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


def generate_config(path: Path) -> Config:
    """
    Given a file path, walk upwards looking for and applying cascading configs
    """
    path = path.resolve()

    return Config(
        path=path,
        enable=["fixit.rules"],
        disable=[],
    )


def locate_configs(path: Path, root: Optional[Path] = None) -> List[Path]:
    """
    Given a file path, locate all relevant config files in priority order.

    Walking upward from target path, creates a list of candidate paths that exist
    on disk, ordered from nearest/highest priority to further/lowest priority.

    If root is given, only return configs between path and root, ignoring any paths
    outside of root, even if they would contain relevant configs. If given, root must
    contain path.

    Returns a list of config paths in priority order, from highest priority to lowest.
    """
    results: List[Path] = []

    if not path.is_dir():
        path = path.parent

    root = root.resolve() if root is not None else path.root
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
        content = path.read_text()
        data = tomllib.loads(content)
        fixit_data = data.get("tool", {}).get("fixit", {})

        if fixit_data:
            config = RawConfig(path=path, data=fixit_data)
            configs.append(config)

            if config.data.get("root", False):
                break

    return configs
