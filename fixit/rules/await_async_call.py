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
            async def bar():
                await foo()
            """
        ),
        Valid(
            """
            async def foo(): pass
            async def bar():
                x = await foo()
            """
        ),
        Valid(
            """
            async def foo() -> bool: pass
            async def bar():
                while not await foo(): pass
            """
        ),
        Valid(
            """
            import asyncio
            async def foo(): pass
            asyncio.run(foo())
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            async def foo(): pass
            async def bar():
                foo()
            """,
            kind="IG31",
            expected_replacement="""
            async def foo(): pass
            async def bar():
                await foo()
            """,
        ),
        Invalid(
            """
            class Foo:
                async def _attr(self): pass
            obj = Foo()
            obj._attr
            """,
            kind="IG31",
            expected_replacement="""
            class Foo:
                async def _attr(self): pass
            obj = Foo()
            await obj._attr
            """,
        ),
        Invalid(
            """
            class Foo:
                async def _method(self): pass
            obj = Foo()
            obj._method()
            """,
            kind="IG31",
            expected_replacement="""
            class Foo:
                async def _method(self): pass
            obj = Foo()
            await obj._method()
            """,
        ),
        Invalid(
            """
            class Foo:
                async def _method(self): pass
            obj = Foo()
            result = obj._method()
            """,
            kind="IG31",
            expected_replacement="""
            class Foo:
                async def _method(self): pass
            obj = Foo()
            result = await obj._method()
            """,
        ),
        Invalid(
            """
            class Foo:
                async def bar(): pass
            class NodeUser:
                async def get():
                    do_stuff()
                    return Foo()
            user = NodeUser.get().bar()
            """,
            kind="IG31",
            expected_replacement="""
            class Foo:
                async def bar(): pass
            class NodeUser:
                async def get():
                    do_stuff()
                    return Foo()
            user = await NodeUser.get().bar()
            """,
        ),
        Invalid(
            """
            class Foo:
                async def _attr(self): pass
            obj = Foo()
            attribute = obj._attr
            """,
            kind="IG31",
            expected_replacement="""
            class Foo:
                async def _attr(self): pass
            obj = Foo()
            attribute = await obj._attr
            """,
        ),
        Invalid(
            code="""
            async def foo() -> bool: pass
            x = True
            if x and foo(): pass
            """,
            kind="IG31",
            expected_replacement="""
            async def foo() -> bool: pass
            x = True
            if x and await foo(): pass
            """,
        ),
        Invalid(
            code="""
            async def foo() -> bool: pass
            x = True
            are_both_true = x and foo()
            """,
            kind="IG31",
            expected_replacement="""
            async def foo() -> bool: pass
            x = True
            are_both_true = x and await foo()
            """,
        ),
        Invalid(
            """
            async def foo() -> bool: pass
            if foo():
                do_stuff()
            """,
            "IG31",
            expected_replacement="""
            async def foo() -> bool: pass
            if await foo():
                do_stuff()
            """,
        ),
        Invalid(
            """
            async def foo() -> bool: pass
            if not foo():
                do_stuff()
            """,
            "IG31",
            expected_replacement="""
            async def foo() -> bool: pass
            if not await foo():
                do_stuff()
            """,
        ),
        Invalid(
            """
            class Foo:
                async def _attr(self): pass
                def bar(self):
                    if self._attr: pass
            """,
            "IG31",
            expected_replacement="""
            class Foo:
                async def _attr(self): pass
                def bar(self):
                    if await self._attr: pass
            """,
        ),
        Invalid(
            """
            class Foo:
                async def _attr(self): pass
                def bar(self):
                    if not self._attr: pass
            """,
            "IG31",
            expected_replacement="""
            class Foo:
                async def _attr(self): pass
                def bar(self):
                    if not await self._attr: pass
            """,
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

    def _get_awaitable_replacement(self, node: cst.CSTNode) -> Optional[cst.CSTNode]:
        annotation = self._get_type_metadata(node)
        if annotation is not None and self._is_callable(annotation):
            return_type = self._get_callable_return_type(annotation)
            annotation = return_type
        if annotation is not None and annotation.startswith("typing.Coroutine"):
            if isinstance(node, cst.BaseExpression):
                return cst.Await(expression=node)
        return None

    def _get_async_attr_replacement(self, node: cst.Attribute) -> Optional[cst.CSTNode]:
        value = node.value
        if m.matches(value, m.Call()):
            value = cast(cst.Call, value)
            value_replacement = self._get_async_call_replacement(value)
            if value_replacement is not None:
                return node.with_changes(value=value_replacement)
        return self._get_awaitable_replacement(node)

    def _get_async_call_replacement(self, node: cst.Call) -> Optional[cst.CSTNode]:
        func = node.func
        if m.matches(func, m.Attribute()):
            func = cast(cst.Attribute, func)
            attr_func_replacement = self._get_async_attr_replacement(func)
            if attr_func_replacement is not None:
                return node.with_changes(func=attr_func_replacement)
        return self._get_awaitable_replacement(node)

    def _get_async_name_replacement(self, node: cst.Name) -> Optional[cst.CSTNode]:
        return self._get_awaitable_replacement(node)

    def _get_async_expr_replacement(self, node: cst.CSTNode) -> Optional[cst.CSTNode]:
        if m.matches(node, m.Call()):
            node = cast(cst.Call, node)
            return self._get_async_call_replacement(node)
        elif m.matches(node, m.Attribute()):
            node = cast(cst.Attribute, node)
            return self._get_async_attr_replacement(node)
        elif m.matches(node, m.UnaryOperation(operator=m.Not())):
            node = cast(cst.UnaryOperation, node)
            replacement_expression = self._get_async_expr_replacement(node.expression)
            if replacement_expression is not None:
                return node.with_changes(expression=replacement_expression)
        elif m.matches(node, m.BooleanOperation()):
            node = cast(cst.BooleanOperation, node)
            left_replacement = self._get_async_expr_replacement(node.left)
            if left_replacement is not None:
                return node.with_changes(left=left_replacement)
            right_replacement = self._get_async_expr_replacement(node.right)
            if right_replacement is not None:
                return node.with_changes(right=right_replacement)
        return None

    def _get_async_assign_replacement(self, node: cst.Assign) -> Optional[cst.CSTNode]:
        return self._get_async_expr_replacement(node.value)

    def visit_If(self, node: cst.If) -> None:
        replacement_test = self._get_async_expr_replacement(node.test)
        if replacement_test is not None:
            replacement = node.with_changes(test=replacement_test)
            self.report(node, replacement=replacement)

    def visit_While(self, node: cst.While) -> None:
        if self._get_async_expr_replacement(node.test):
            self.report(node)

    def visit_Assign(self, node: cst.Assign) -> None:
        replacement_value = self._get_async_assign_replacement(node)
        if replacement_value is not None:
            replacement = node.with_changes(value=replacement_value)
            self.report(node, replacement=replacement)

    def visit_Expr(self, node: cst.Expr) -> None:
        replacement_value = self._get_async_expr_replacement(node.value)
        if replacement_value is not None:
            replacement = node.with_changes(value=replacement_value)
            self.report(node, replacement=replacement)
