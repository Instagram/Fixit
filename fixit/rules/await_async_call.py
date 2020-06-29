# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
from typing import Match, Optional, cast

import libcst as cst
import libcst.matchers as m
from libcst.metadata import TypeInferenceProvider

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class AwaitAsyncCallRule(CstLintRule):
    MESSAGE: str = (
        "IG31 Async function call will only be executed with `await` statement. Do you forget to add `await`? "
        + "If you intend to not await, please add comment to disable this warning: # lint-fixme: IG31 "
    )

    METADATA_DEPENDENCIES = (TypeInferenceProvider,)

    VALID = [
        Valid(
            """
            async def async_func():
                await async_foo()
            """
        ),
        Valid(
            """
            def foo(): pass
            foo()
            """
        ),
        Valid(
            """
            async def foo(): pass
            await foo()
            """
        ),
        Valid(
            """
            async def foo(): pass
            x = await foo()
            """
        ),
        Valid(
            """
            async def foo() -> bool: pass
            while not await foo(): pass
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
        async def foo(): pass
        foo()
        """,
            kind="IG31",
        ),
        Invalid(
            """
        class Foo:
            async def _attr(self): pass
        obj = Foo()
        obj._attr
        """,
            kind="IG31",
        ),
        Invalid(
            """
        class Foo:
            async def _method(self): pass
        obj = Foo()
        obj._method()
        """,
            kind="IG31",
        ),
        Invalid(
            """
        class Foo:
            async def _method(self): pass
        obj = Foo()
        result = obj._method()
        """,
            kind="IG31",
        ),
        Invalid(
            """
        class Foo:
            async def bar(): pass
        class NodeUser:
            async def get():
                do_stuff()
                return Foo()
        user = (
            NodeUser.get()
            .bar()
        )
        """,
            kind="IG31",
        ),
        Invalid(
            """
        class Foo:
            async def _attr(self): pass
        obj = Foo()
        attribute = obj._attr
        """,
            kind="IG31",
        ),
        Invalid(
            code="""
            async def foo() -> bool: pass
            x = True
            if x and foo(): pass
            """,
            kind="IG31",
        ),
        Invalid(
            code="""
            async def foo() -> bool: pass
            x = True
            are_both_true = x and foo()
            """,
            kind="IG31",
        ),
        Invalid(
            """
            async def foo() -> bool: pass
            if foo():
                do_stuff()
            """,
            "IG31",
        ),
        Invalid(
            """
            async def foo() -> bool: pass
            if not foo():
                do_stuff()
            """,
            "IG31",
        ),
        Invalid(
            """
            class Foo:
                async def _attr(self): pass
                def bar(self):
                    if self._attr: pass
            """,
            "IG31",
        ),
        Invalid(
            """
            class Foo:
                async def _attr(self): pass
                def bar(self):
                    if not self._attr: pass
            """,
            "IG31",
        ),
        Invalid(
            """
            async def foo(): pass
            while foo():
                do_stuff()
            """,
            "IG31",
        ),
        Invalid(
            """
            async def foo(): pass
            while not foo():
                do_stuff()
            """,
            "IG31",
        ),
        Invalid(
            """
            class Foo:
                async def _attr(self): pass
                def bar(self):
                    while self._attr:
                        do_stuff()
            """,
            "IG31",
        ),
    ]

    def _get_type_metadata(self, node: cst.CSTNode) -> Optional[str]:
        return self.get_metadata(TypeInferenceProvider, node, None)

    @staticmethod
    def _get_callable_return_type(annotation: str) -> Optional[str]:
        callable_pattern = re.compile(
            "typing\\.Callable\\(.*\\)\\[\\[.*\\], (.*)\\[.*\\]\\]"
        )
        match: Optional[Match[str]] = callable_pattern.match(annotation)
        if match is not None:
            return match.group(1)
        return None

    @staticmethod
    def _is_callable(annotation: str) -> bool:
        return annotation.startswith("typing.Callable")

    def _is_awaitable(self, node: cst.CSTNode) -> bool:
        annotation = self._get_type_metadata(node)
        if annotation is not None and self._is_callable(annotation):
            return_type = self._get_callable_return_type(annotation)
            annotation = return_type
        return annotation is not None and (
            annotation.startswith("typing.Coroutine")
            or annotation.startswith("typing.Awaitable")
        )

    def _is_async_attr(self, node: cst.Attribute) -> bool:
        value = node.value
        if m.matches(value, m.Call()):
            value = cast(cst.Call, value)
            return self._is_async_call(value)
        return self._is_awaitable(node)

    def _is_async_call(self, node: cst.Call) -> bool:
        func = node.func
        if m.matches(func, m.Attribute()):
            func = cast(cst.Attribute, func)
            return self._is_async_attr(func)
        return self._is_awaitable(node)

    def _is_async_name(self, node: cst.Name) -> bool:
        return self._is_awaitable(node)

    def _is_async_expr(self, node: cst.CSTNode) -> bool:
        if m.matches(node, m.Call()):
            node = cast(cst.Call, node)
            return self._is_async_call(node)
        elif m.matches(node, m.Attribute()):
            node = cast(cst.Attribute, node)
            return self._is_async_attr(node)
        elif m.matches(node, m.UnaryOperation(operator=m.Not())):
            node = cast(cst.UnaryOperation, node)
            return self._is_async_expr(node.expression)
        elif m.matches(node, m.BooleanOperation()):
            node = cast(cst.BooleanOperation, node)
            return self._is_async_expr(node.left) or self._is_async_expr(node.right)
        return False

    def _is_async_assign(self, node: cst.Assign) -> bool:
        return self._is_async_expr(node.value)

    def visit_If(self, node: cst.If) -> None:
        if self._is_async_expr(node.test):
            self.report(node)

    def visit_While(self, node: cst.While) -> None:
        if self._is_async_expr(node.test):
            self.report(node)

    def visit_Assign(self, node: cst.Assign) -> None:
        if self._is_async_assign(node):
            self.report(node)

    def visit_Expr(self, node: cst.Expr) -> None:
        if self._is_async_expr(node.value):
            self.report(node)
