# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Optional, List

import libcst as cst
import libcst.matchers as m
from libcst.metadata import TypeInferenceProvider, FullyQualifiedNameProvider

from fixit import (
    CodePosition,
    CodeRange,
    CstLintRule,
    InvalidTestCase as Invalid,
    ValidTestCase as Valid,
)

from rich import print

class PyreMetadataRule(CstLintRule):
    """ """

    MESSAGE = "Something something pyre"

    VALID: List[Valid] = []

    INVALID: List[Invalid] = []

    METADATA_DEPENDENCIES = (
        # TypeInferenceProvider,
        FullyQualifiedNameProvider,
    )

    def __init__(self) -> None:
        super().__init__()

    def visit_Attribute(self, node: cst.Attribute) -> Optional[bool]:
        pass
        # print(node)
        # print(self.get_metadata(FullyQualifiedNameProvider, node))

    def visit_Name(self, node: cst.Name) -> Optional[bool]:
        pass
        # print(node)
        # print(self.get_metadata(TypeInferenceProvider, node))
