from dataclasses import replace
from typing import ClassVar, Collection, Iterable, List, Optional, Set, TypeVar, Union
from libcst import (
    BatchableCSTVisitor,
    CSTNode,
    RemovalSentinel,
    FlattenSentinel,
    parse_module,
)
from libcst.metadata import (
    CodeRange,
    PositionProvider,
    ProviderT,
    CodePosition,
    MetadataWrapper,
)

from fixit.types import LintViolation, FileContent
from . import LintRule, LintRunner


class CSTLintRunner(LintRunner["CSTLintRule"]):
    @classmethod
    def collect_violations(
        cls, source: FileContent, rules: Collection["CSTLintRule"]
    ) -> Iterable[LintViolation]:
        mod = MetadataWrapper(parse_module(source), unsafe_skip_copy=True)
        mod.visit_batched(rules)
        for rule in rules:
            for violation in rule._violations:
                yield violation


class CSTLintRule(LintRule, BatchableCSTVisitor):
    METADATA_DEPENDENCIES: ClassVar[Collection[ProviderT]] = (PositionProvider,)

    _runner = CSTLintRunner

    def report(
        self,
        node: CSTNode,
        message: Optional[str] = None,
        *,
        position: Optional[Union[CodePosition, CodeRange]] = None,
        replacement: Optional[Union[CSTNode, RemovalSentinel, FlattenSentinel]] = None,
    ) -> None:
        rule_name = type(self).__name__
        if not message:
            # backwards compat with Fixit 1.0 api
            message = getattr(self, "MESSAGE", None)
            if not message:
                raise ValueError(f"No message provided in {rule_name}")

        if position is None:
            position = self.get_metadata(PositionProvider, node)
        elif isinstance(position, CodePosition):
            end = replace(position, line=position.line + 1, column=0)
            position = CodeRange(start=position, end=end)
        self._violations.append(
            LintViolation(
                rule_name,
                range=position,
                message=message,
                autofixable=bool(replacement),
            )
        )


CstLintRule = CSTLintRule
