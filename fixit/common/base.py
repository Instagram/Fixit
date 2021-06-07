# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
from abc import ABCMeta
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type, Union

import libcst as cst
from libcst import BatchableCSTVisitor
from libcst.metadata import (
    BaseMetadataProvider,
    CodePosition,
    MetadataWrapper,
    PositionProvider,
    TypeInferenceProvider,
)

from fixit.common.report import BaseLintRuleReport, CstLintRuleReport


if TYPE_CHECKING:
    from libcst.metadata.base_provider import ProviderT

    from fixit.common.pseudo_rule import PseudoLintRule


LintRuleT = Union[Type["CstLintRule"], Type["PseudoLintRule"]]

CACHE_DEPENDENT_PROVIDERS: Tuple["ProviderT"] = (TypeInferenceProvider,)


def _get_code(message: str, class_name: str) -> str:
    """Extract the lint code from the beginning of the lint message."""
    # TODO: Deprecate this function.
    code_match = re.match(r"^(?P<code>IG\d+) \S", message)
    if not code_match:
        return class_name
    return code_match.group("code")


DEFAULT_PACKAGES = ["fixit.rules"]
DEFAULT_PATTERNS = [f"@ge{''}nerated", "@nolint"]


@dataclass(frozen=True)
class LintConfig:
    allow_list_rules: List[str] = field(default_factory=list)
    block_list_patterns: List[str] = field(default_factory=lambda: DEFAULT_PATTERNS)
    block_list_rules: List[str] = field(default_factory=list)
    fixture_dir: str = "./fixtures"
    use_noqa: bool = False
    formatter: List[str] = field(default_factory=list)
    packages: List[str] = field(default_factory=lambda: DEFAULT_PACKAGES)
    repo_root: str = "."
    rule_config: Dict[str, Dict[str, object]] = field(default_factory=dict)
    inherit: bool = False


class BaseContext:
    file_path: Path
    config: LintConfig
    reports: List[BaseLintRuleReport]

    def __init__(self, file_path: Path, config: LintConfig) -> None:
        self.file_path = file_path
        self.config = config
        self.reports = []

    @property
    def in_tests(self) -> bool:
        return self.file_path.name == "tests.py" or "tests" in self.file_path.parts

    @property
    def in_scripts(self) -> bool:
        return Path("distillery/scripts") in self.file_path.parents


class CstContext(BaseContext):
    wrapper: MetadataWrapper
    _source: bytes
    node_stack: List[cst.CSTNode]

    def __init__(
        self,
        wrapper: MetadataWrapper,
        source: bytes,
        file_path: Path,
        config: LintConfig,
    ) -> None:
        super().__init__(file_path, config)
        self.wrapper = wrapper
        # Keep the source around so we can use it in autofix diff generation. This is
        # private because lint rules should use the CST tree, not the source code. If we
        # exposed the source, it'd be providing rope for people to hang themselves with.
        self._source = source
        self.node_stack = []


class CstLintRule(BatchableCSTVisitor, metaclass=ABCMeta):
    #: a short message in one or two sentences show to user when the rule is violated.
    MESSAGE: Optional[str] = None

    METADATA_DEPENDENCIES: Tuple[Type[BaseMetadataProvider], ...] = (PositionProvider,)

    def __init__(self, context: CstContext) -> None:
        super().__init__()
        self.context = context

    def should_skip_file(self) -> bool:
        return False

    def report(
        self,
        node: cst.CSTNode,
        message: Optional[str] = None,
        *,
        position: Optional[CodePosition] = None,
        replacement: Optional[
            Union[cst.CSTNode, cst.RemovalSentinel, cst.FlattenSentinel]
        ] = None,
    ) -> None:
        """
        Report a lint violation for a given node. Optionally specify a custom
        position to report an error at or a replacement node for an auto-fix.
        """
        if position is None:
            position = self.context.wrapper.resolve(PositionProvider)[node].start

        if message is None:
            message = self.MESSAGE
            if message is None:
                raise Exception(f"No lint message was provided to rule: {self}")
        report = CstLintRuleReport(
            file_path=self.context.file_path,
            node=node,
            # TODO deprecate _get_code() completely and replace with self.__class__.__name__
            code=_get_code(message, self.__class__.__name__),
            message=message,
            line=position.line,
            # libcst columns are 0-indexed but arc is 1-indexed
            column=(position.column + 1),
            module=self.context.wrapper,
            module_bytes=self.context._source,
            replacement_node=replacement,
        )
        self.context.reports.append(report)

    @classmethod
    def requires_metadata_caches(cls) -> bool:
        return any(
            p in CACHE_DEPENDENT_PROVIDERS for p in cls.get_inherited_dependencies()
        )
