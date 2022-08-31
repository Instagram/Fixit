# Copyright (c) Meta Platforms, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Collection, Iterable, List

from fixit.rule import LintRule

from .types import Config

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
