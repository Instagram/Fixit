# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
import libcst as cst
from libcst.metadata import QualifiedNameProvider

from fixit import CstLintRule, InvalidTestCase, ValidTestCase


class UseAsyncSleepInAsyncDefRule(CstLintRule):
    """
    Detect if asyncio.sleep is used in an async function
    """

    MESSAGE: str = "Use asyncio.sleep in async function"
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)
    VALID = [
        ValidTestCase(
            """
            import time
            def func():
                time.sleep(1)
            """
        ),
        ValidTestCase(
            """
            from time import sleep
            def func():
                sleep(1)
            """
        ),
        ValidTestCase(
            """
            from asyncio import sleep
            async def func():
                await sleep(1)
            """
        ),
        ValidTestCase(
            """
            import asyncio
            async def func():
                await asyncio.sleep(1)
            """
        ),
        ValidTestCase(
            """
            import time
            import asyncio
            def func():
                time.sleep(1)
            """
        ),
        ValidTestCase(
            """
            import time
            import asyncio
            async def func():
                await asyncio.sleep(1)
            """
        ),
        ValidTestCase(
            """
            import time
            import asyncio
            async def func():
                fut = asyncio.sleep(1)
                await fut
            """
        ),
        ValidTestCase(
            """
            import something
            async def func():
                something.sleep(3)
            """
        ),
    ]
    INVALID = [
        InvalidTestCase(
            """
            import time
            async def func():
                time.sleep(1)
            """
        ),
        InvalidTestCase(
            """
            from time import sleep
            async def func():
                sleep(1)
            """
        ),
        InvalidTestCase(
            """
            from time import sleep
            import asyncio
            async def func():
                sleep(2)
                asyncio.sleep(1)
            """
        ),
        InvalidTestCase(
            """
            from asyncio import sleep
            import time
            async def func():
                sleep(2)
                time.sleep(1)
            """
        ),
    ]

    def __init__(self):
        super().__init__()
        # is async func
        self.async_func = False

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.async_func = node.asynchronous is not None

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.async_func = False

    def visit_Call(self, node: cst.Call) -> None:
        if not self.async_func:
            return

        metadata = list(self.get_metadata(QualifiedNameProvider, node))
        if not metadata:
            return

        func_full_name = metadata[0].name
        if func_full_name != "time.sleep":
            return

        self.report(node, self.MESSAGE)
