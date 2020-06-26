# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import json
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Type, cast

import libcst as cst
from libcst.metadata import BaseMetadataProvider, MetadataWrapper, TypeInferenceProvider
from libcst.metadata.type_inference_provider import PyreData


def _dedent(src: str) -> str:
    src = re.sub(r"\A\n", "", src)
    return textwrap.dedent(src)


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


@dataclass(frozen=True)
class ValidTypeDependentTestCase(ValidTestCase):
    type_inference_wrapper: MetadataWrapper = MetadataWrapper(cst.Module([]))


@dataclass(frozen=True)
class InvalidTypeDependentTestCase(InvalidTestCase):
    type_inference_wrapper: MetadataWrapper = MetadataWrapper(cst.Module([]))


def valid_type_dependent_test_case_helper(
    code: str, pyre_json_data_path: Path
) -> ValidTypeDependentTestCase:
    module = cst.parse_module(_dedent(code))
    pyre_json_data: PyreData = json.loads(pyre_json_data_path.read_text())
    provider_type = TypeInferenceProvider
    type_inference_wrapper = MetadataWrapper(
        module=module,
        cache={cast(Type[BaseMetadataProvider[object]], provider_type): pyre_json_data},
    )
    return ValidTypeDependentTestCase(
        code=code, type_inference_wrapper=type_inference_wrapper
    )


def invalid_type_dependent_test_case_helper(
    code: str,
    kind: str,
    pyre_json_data_path: Path,
    line: Optional[int] = None,
    column: Optional[int] = None,
    expected_replacement: Optional[str] = None,
) -> InvalidTypeDependentTestCase:
    module = cst.parse_module(_dedent(code))
    pyre_json_data: PyreData = json.loads(pyre_json_data_path.read_text())
    provider_type = TypeInferenceProvider
    type_inference_wrapper = MetadataWrapper(
        module=module,
        cache={cast(Type[BaseMetadataProvider[object]], provider_type): pyre_json_data},
    )
    return InvalidTypeDependentTestCase(
        code=code,
        kind=kind,
        line=line,
        column=column,
        expected_replacement=expected_replacement,
        type_inference_wrapper=type_inference_wrapper,
    )
