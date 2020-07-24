# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Dict, Optional, Sequence, Union, cast

import libcst as cst
import libcst.matchers as m
from libcst.helpers import get_full_name_for_node
from libcst.metadata import TypeInferenceProvider

from fixit.common.base import CstLintRule
from fixit.common.utils import InvalidTestCase as Invalid, ValidTestCase as Valid


class AwaitAsyncCallRule(CstLintRule):
    MESSAGE: str = (
        "IG31 Async function call will only be executed with `await` statement. Did you forget to add `await`? "
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
        # Case where only cst.Attribute node's `attr` returns awaitable
        Invalid(
            """
            class Foo:
                async def _attr(self): pass
            def bar() -> Foo:
                return Foo()
            attribute = bar()._attr
            """,
            "IG31",
            expected_replacement="""
            class Foo:
                async def _attr(self): pass
            def bar() -> Foo:
                return Foo()
            attribute = await bar()._attr
            """,
        ),
        # Case where only cst.Attribute node's `value` returns awaitable
        Invalid(
            """
            class Foo:
                def _attr(self): pass
            async def bar():
                await do_stuff()
                return Foo()
            attribute = bar()._attr
            """,
            "IG31",
            expected_replacement="""
            class Foo:
                def _attr(self): pass
            async def bar():
                await do_stuff()
                return Foo()
            attribute = await bar()._attr
            """,
        ),
        Invalid(
            """
            async def bar() -> bool: pass
            while bar(): pass
            """,
            "IG31",
            expected_replacement="""
            async def bar() -> bool: pass
            while await bar(): pass
            """,
        ),
        Invalid(
            """
            async def bar() -> bool: pass
            while not bar(): pass
            """,
            "IG31",
            expected_replacement="""
            async def bar() -> bool: pass
            while not await bar(): pass
            """,
        ),
    ]

    @staticmethod
    def _is_awaitable_callable(annotation: str) -> bool:
        if not annotation.startswith("typing.Callable"):
            # Exit early if this is not even a `typing.Callable` annotation.
            return False
        try:
            # Wrap this in a try-except since the type annotation may not be parse-able as a module.
            # If it is not parse-able, we know it's not what we are looking for anyway, so return `False`.
            parsed_ann = cst.parse_module(annotation)
        except Exception:
            return False
        # If passed annotation does not match the expected annotation structure for a `typing.Callable` with
        # typing.Coroutine as the return type, matched_callable_ann will simply be `None`.
        # The expected structure of an awaitable callable annotation from Pyre is: typing.Callable()[[...], typing.Coroutine[...]]
        matched_callable_ann: Optional[
            Dict[str, Union[Sequence[cst.CSTNode], cst.CSTNode]]
        ] = m.extract(
            parsed_ann,
            m.Module(
                body=[
                    m.SimpleStatementLine(
                        body=[
                            m.Expr(
                                value=m.Subscript(
                                    slice=[
                                        m.SubscriptElement(),
                                        m.SubscriptElement(
                                            slice=m.Index(
                                                value=m.Subscript(
                                                    value=m.SaveMatchedNode(
                                                        m.Attribute(),
                                                        "base_return_type",
                                                    )
                                                )
                                            )
                                        ),
                                    ],
                                )
                            )
                        ]
                    ),
                ]
            ),
        )
        if (
            matched_callable_ann is not None
            and "base_return_type" in matched_callable_ann
        ):
            base_return_type = get_full_name_for_node(
                cst.ensure_type(matched_callable_ann["base_return_type"], cst.CSTNode)
            )
            return (
                base_return_type is not None and base_return_type == "typing.Coroutine"
            )
        return False

    def _get_awaitable_replacement(self, node: cst.CSTNode) -> Optional[cst.CSTNode]:
        annotation = self.get_metadata(TypeInferenceProvider, node, None)
        if annotation is not None and (
            annotation.startswith("typing.Coroutine")
            or self._is_awaitable_callable(annotation)
        ):
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
            maybe_left = self._get_async_expr_replacement(node.left)
            maybe_right = self._get_async_expr_replacement(node.right)
            if maybe_left is not None or maybe_right is not None:
                left_replacement = maybe_left if maybe_left is not None else node.left
                right_replacement = (
                    maybe_right if maybe_right is not None else node.right
                )
                return node.with_changes(left=left_replacement, right=right_replacement)
        return None

    def _maybe_autofix_node(self, node: cst.CSTNode, attribute_name: str) -> None:
        replacement_value = self._get_async_expr_replacement(
            getattr(node, attribute_name)
        )
        if replacement_value is not None:
            replacement = node.with_changes(**{attribute_name: replacement_value})
            self.report(node, replacement=replacement)

    def visit_If(self, node: cst.If) -> None:
        self._maybe_autofix_node(node, "test")

    def visit_While(self, node: cst.While) -> None:
        self._maybe_autofix_node(node, "test")

    def visit_Assign(self, node: cst.Assign) -> None:
        self._maybe_autofix_node(node, "value")

    def visit_Expr(self, node: cst.Expr) -> None:
        self._maybe_autofix_node(node, "value")
