# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


def print_color(code: int, message: str) -> None:
    print(f"\033[{code}m{message}\033[00m")


def print_green(message: str) -> None:
    print_color(92, message)


def print_yellow(message: str) -> None:
    print_color(93, message)


def print_cyan(message: str) -> None:
    print_color(96, message)


def print_red(message: str) -> None:
    print_color(91, message)


def snake_to_camelcase(name: str) -> str:
    """Convert snake-case string to camel-case string."""
    return "".join(n.capitalize() for n in name.split("_"))
