# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Linting framework built on LibCST, with automatic fixes
"""

__version__ = "0.2.0"

from libcst.metadata import CodePosition, CodeRange

from .api import fixit_bytes, fixit_file, fixit_paths
from .rule import LintRule
from .rule.cst import CSTLintRule, CstLintRule
from .testing import InvalidTestCase, ValidTestCase
from .types import Config, FileContent, Result

__all__ = [
    "__version__",
    "fixit_bytes",
    "fixit_file",
    "fixit_paths",
    "LintRule",
    "CSTLintRule",
    "CstLintRule",
    "InvalidTestCase",
    "ValidTestCase",
    "Config",
    "FileContent",
    "Result",
    "CodeRange",
    "CodePosition",
]
