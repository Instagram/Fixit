# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


from fixit import CstLintRule, InvalidTestCase as Invalid, ValidTestCase as Valid


"""
This is a model rule file for adding a new rule to fixit module
"""


class Rule(CstLintRule):
    """
    docstring or new_rule description
    """

    MESSAGE = "Enter rule description message"

    VALID = [Valid("'example'")]

    INVALID = [Invalid("'example'")]
