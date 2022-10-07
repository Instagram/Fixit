# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import abc
import ast
import io
import tokenize
from pathlib import Path
from typing import Iterable, Optional

from fixit.common.report import BaseLintRuleReport


class PseudoContext:
    """
    Contains information about the file that `PseudoLintRule.lint_file` should evaluate.
    """

    def __init__(
        self,
        file_path: Path,
        source: bytes,
        tokens: Optional[Iterable[tokenize.TokenInfo]] = None,
        ast_tree: Optional[ast.Module] = None,
    ) -> None:
        self.file_path: Path = file_path
        self.source: bytes = source
        self._tokens: Optional[Iterable[tokenize.TokenInfo]] = tokens
        self._ast_tree: Optional[ast.Module] = ast_tree

    @property
    def tokens(self) -> Iterable[tokenize.TokenInfo]:
        tokens = self._tokens
        if tokens is not None:
            return tokens
        tokens = tuple(tokenize.tokenize(io.BytesIO(self.source).readline))
        self._tokens = tokens
        return tokens

    @property
    def ast_tree(self) -> ast.Module:
        ast_tree = self._ast_tree
        if ast_tree is not None:
            return ast_tree
        ast_tree = ast.parse(self.source)
        self._ast_tree = ast_tree
        return ast_tree


class PseudoLintRule(abc.ABC):
    """
    Represents a lint rule (or a group of lint rules) that can't be represented by a
    normal lint rule. These "pseudo" lint rules receive information about the file from
    the `PsuedoContext`.

    This API is much more flexible than the normal lint rule API, but that comes at a
    (potentially large) performance cost. Because the lint framework does not control
    traversal of the syntax tree, it cannot batch the execution of these rules alongside
    other lint rules.

    This API is used for compatibility with Flake8 rules.
    """

    def __init__(self, context: PseudoContext) -> None:
        self.context: PseudoContext = context

    @abc.abstractmethod
    def lint_file(self) -> Iterable[BaseLintRuleReport]:
        ...
