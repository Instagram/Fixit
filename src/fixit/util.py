# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import cast, Generator, Generic, TypeVar, Union

Yield = TypeVar("Yield")
Send = TypeVar("Send")
Return = TypeVar("Return")

Sentinel = object()


class capture(Generic[Yield, Send, Return]):
    """
    Wrap a generator, and capture it's final return value in the ``.result`` property.

    Example usage:

    .. code:: python

        generator = capture( fixit_bytes(...) )
        for result in generator:  # LintViolation
            ...
        result = generator.result  # FileContent
    """

    def __init__(self, generator: Generator[Yield, Send, Return]) -> None:
        self.generator = generator
        self._result: Union[Return, object] = Sentinel

    def __iter__(self) -> Generator[Yield, Send, Return]:
        self._result = yield from self.generator
        return self._result

    @property
    def result(self) -> Return:
        if self._result is Sentinel:
            raise ValueError("Generator hasn't completed")
        return cast(Return, self._result)
