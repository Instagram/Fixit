# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Triggers built-in lint rules
class Foo(object):
    def bar(self, value: str) -> str:
        return "value is {}".format(value)

class Bar(object):
    pass
