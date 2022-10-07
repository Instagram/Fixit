# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from collections import defaultdict
from typing import Collection, Dict, Iterable, List, Type

from .rule import LintRule, LintRunner
from .types import FileContent, LintViolation


def collect_violations(
    source: FileContent, rules: Collection[LintRule]
) -> Iterable[LintViolation]:
    # partition rules by LintRunner:
    rules_by_runner: Dict[Type[LintRunner], List[LintRule]] = defaultdict(lambda: [])
    for rule in rules:
        rules_by_runner[rule._runner].append(rule)

    for runner_cls, rules in rules_by_runner.items():
        runner = runner_cls()
        yield from runner.collect_violations(source, rules)
