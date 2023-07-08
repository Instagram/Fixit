# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Linting framework built on LibCST, with automatic fixes
"""

from .__version__ import __version__
from .api import fixit_bytes, fixit_file, fixit_paths, print_result
from .format import Formatter
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
from .rule import LintRule
from .testing import Invalid, Valid

# DEPRECATED: aliases to 0.x names
# TODO: create lint rules to fix references
CstLintRule = LintRule
CSTLintRule = LintRule
InvalidTestCase = Invalid
ValidTestCase = Valid

__all__ = [
    "__version__",
    "fixit_bytes",
    "fixit_file",
    "fixit_paths",
    "print_result",
    "CSTLintRule",
    "CstLintRule",
    "Formatter",
    "LintRule",
    "LintViolation",
    "Invalid",
    "InvalidTestCase",
    "Valid",
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
