# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Triggers built-in lint rules
class Foo(object):
    def bar(self, value: str) -> str:
        return "value is {}".format(value)

# lint-fixme: SomethingUnrelated
class Bar(object):
    pass


# lint-ignore
class Phi(object):
    pass


# lint-fixme: NoInheritFromObject
class Rho(object):
    pass


class Zeta(object):  # lint-ignore NoInheritFromObject
    pass
