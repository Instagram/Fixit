# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import cast, Generator, Generic, Optional, TypeVar, Union

Yield = TypeVar("Yield")
Send = TypeVar("Send")
Return = TypeVar("Return")

Sentinel = object()


class capture(Generic[Yield, Send, Return]):
    """
    Wrap a generator, and capture it's final return value in the :attr:`result` property.

    Allows sending values back to the generator using the :meth:`respond` method.

    Example usage:

    .. code:: python

        generator = capture( fixit_bytes(...) )
        for result in generator:  # LintViolation
            ...
            generator.respond(...)  # optional

        result = generator.result  # FileContent
    """

    def __init__(self, generator: Generator[Yield, Send, Return]) -> None:
        self.generator = generator
        self._send: Optional[Send] = None
        self._result: Union[Return, object] = Sentinel

    def __iter__(self) -> Generator[Yield, Send, Return]:
        try:
            while True:
                value = self.generator.send(cast(Send, self._send))
                self._send = None
                answer = yield value
                if answer is not None:
                    self._send = answer
        except StopIteration as stop:
            self._result = cast(Return, stop.value)
        return self._result

    def respond(self, answer: Send) -> None:
        """
        Send a value back to the generator in the next iteration.

        Can be called while iterating on the wrapped generator object.
        """
        self._send = answer

    @property
    def result(self) -> Return:
        """
        Contains the final return value from the wrapped generator, if any.
        """
        if self._result is Sentinel:
            raise ValueError("Generator hasn't completed")
        return cast(Return, self._result)
