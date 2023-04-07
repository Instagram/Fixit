# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
import libcst as cst
from libcst import matchers as m
from libcst.metadata import ParentNodeProvider

from fixit import CstLintRule, InvalidTestCase, ValidTestCase


class UseAsyncSleepInAsyncDefRule(CstLintRule):
    """
    Detect if asyncio.sleep is used in an async function
    """

    MESSAGE: str = "Use asyncio.sleep in async function"

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
            from asyncio import *
            async def func():
                await sleep(1)
            """
        ),
        # don't care if await if missing
        ValidTestCase(
            """
            import time
            from asyncio import *
            async def func():
                sleep(1)
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
            from time import *
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
    METADATA_DEPENDENCIES = (ParentNodeProvider,)

    def __init__(self):
        super().__init__()
        """
        Scenarios:
        0. 'time' is not imported or not an async func  -> skip lint
        1. no alias 'sleep' is imported -> 'asyncio.sleep' need to be called
        2. alias 'sleep' is imported, check if imported from asyncio
            a. If yes -> 'sleep' need to be called alone. e.g. sleep(..), not xx.sleep(..)
            b. If no -> 'asyncio.sleep' need to be called
        """
        # is time imported
        self.time_imported = False
        # is async func
        self.async_func = False
        # is sleep imported as an alias
        self.alias_sleep_imported = False
        # is sleep improted as an alias from asyncio
        self.sleep_from_asyncio = False
        # is current processing an object with name == sleep
        self.is_processing_sleep = False

    def visit_Import(self, node: cst.Import) -> None:
        self.time_imported = self.time_imported or any(
            alias.name.value == "time" for alias in node.names
        )

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if (
            node.module
            and node.module.value != "asyncio"
            and node.module.value != "time"
        ):
            return

        self.time_imported = self.time_imported or (
            node.module and node.module.value == "time"
        )
        sleep_in_this_module = isinstance(node.names, cst.ImportStar) or any(
            alias.name.value == "sleep" for alias in node.names
        )
        self.alias_sleep_imported = self.alias_sleep_imported or sleep_in_this_module
        self.sleep_from_asyncio = self.sleep_from_asyncio or (
            True
            if sleep_in_this_module and node.module and node.module.value == "asyncio"
            else False
        )

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.async_func = node.asynchronous

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.async_func = False

    def visit_Name(self, node: cst.Name) -> None:
        self.is_processing_sleep = self.is_processing_sleep or (
            node and node.value == "sleep"
        )

    def visit_Call(self, node: cst.Call) -> None:
        self.is_processing_sleep = False

    def leave_Call(self, node: cst.Call) -> None:
        if (
            not self.is_processing_sleep
            or not self.async_func
            or not self.time_imported
        ):
            return

        correct: bool = False
        if not self.alias_sleep_imported or not self.sleep_from_asyncio:
            # need to be called with asyncio.sleep
            correct = m.matches(
                node,
                m.Call(func=m.Attribute(value=m.Name("asyncio"), attr=m.Name("sleep"))),
            )
        else:  # sleep is imported as alias
            if self.sleep_from_asyncio:
                # sleep has to be called with sleep(..)
                correct = isinstance(node.func, cst.Name) and node.func.value == "sleep"

        if not correct:
            self.report(node, self.MESSAGE)
