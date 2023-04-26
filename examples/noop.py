# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fixit import LintRule

class NoOpRule(LintRule):
    MESSAGE = "You shouldn't be seeing this"
    VALID = []
    INVALID = []
