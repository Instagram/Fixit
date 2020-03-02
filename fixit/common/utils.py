# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


def _str_or_any(value: Optional[int]) -> str:
    return "<any>" if value is None else str(value)


@dataclass(frozen=True)
class ValidTestCase:
    code: str
    filename: str = "not/a/real/file/path.py"
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InvalidTestCase:
    code: str
    kind: str
    line: Optional[int] = None
    column: Optional[int] = None
    expected_replacement: Optional[str] = None
    filename: str = "not/a/real/file/path.py"
    config: Mapping[str, Any] = field(default_factory=dict)

    @property
    def expected_str(self) -> str:
        return f"{_str_or_any(self.line)}:{_str_or_any(self.column)}: {self.kind} ..."
