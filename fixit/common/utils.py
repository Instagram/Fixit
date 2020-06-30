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


class FixtureFileNotFoundError(Exception):
    pass


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


def gen_type_inference_wrapper(code: str, pyre_fixture_path: Path) -> MetadataWrapper:
    # Given test case source code and a path to a pyre fixture file, generate a MetadataWrapper for a lint rule test case.
    module = cst.parse_module(_dedent(code))
    provider_type = TypeInferenceProvider
    try:
        pyre_json_data: PyreData = json.loads(pyre_fixture_path.read_text())
    except FileNotFoundError as e:
        raise FixtureFileNotFoundError(
            f"Fixture file not found at {e.filename}. "
            + "Please run `python -m fixit.common.generate_pyre_fixtures <rule>` to generate fixtures."
        )
    return MetadataWrapper(
        module=module,
        cache={cast(Type[BaseMetadataProvider[object]], provider_type): pyre_json_data},
    )
