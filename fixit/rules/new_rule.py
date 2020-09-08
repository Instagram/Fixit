# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst
from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid

class Rule(CstLintRule):
    """
    docstring or new_rule description
    """
    MESSAGE = 'Enter rule description message'

    VALID = [Valid()]

    INVALID = [Invalid()]

