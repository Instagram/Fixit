from collections import defaultdict
from typing import Collection, Dict, Iterable, List, Type

from .rule import LintRule, LintRunner
from .types import Config, FileContent, LintViolation


def collect_rules(config: Config) -> Collection[LintRule]:
    # TODO
    from fixit.rules.use_fstring import UseFstringRule

    return [UseFstringRule()]


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
