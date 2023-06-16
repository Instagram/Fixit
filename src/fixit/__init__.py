# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Linting framework built on LibCST, with automatic fixes
"""

from .__version__ import __version__
from .api import fixit_bytes, fixit_file, fixit_paths, print_result
from .ftypes import (
    CodePosition,
    CodeRange,
    Config,
    FileContent,
    LintViolation,
    Options,
    QualifiedRule,
    Result,
    Tags,
)
from .rule import CSTLintRule, CstLintRule, LintRule
from .testing import InvalidTestCase, ValidTestCase

__all__ = [
    "__version__",
    "fixit_bytes",
    "fixit_file",
    "fixit_paths",
    "print_result",
    "CSTLintRule",
    "CstLintRule",
    "LintRule",
    "LintViolation",
    "InvalidTestCase",
    "ValidTestCase",
    "Config",
    "FileContent",
    "Options",
    "QualifiedRule",
    "Result",
    "Tags",
    "CodeRange",
    "CodePosition",
]
