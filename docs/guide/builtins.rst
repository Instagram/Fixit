
..
   THIS FILE IS GENERATED - DO NOT EDIT BY HAND!
   Run `make html` or `scripts/document_rules.py` to regenerate this file.

.. module:: builtin-rules

Built-in Rules
--------------

- :mod:`fixit.rules`
- :mod:`fixit.upgrade`


``fixit.rules``
^^^^^^^^^^^^^^^

.. automodule:: fixit.rules

- :class:`AvoidOrInExceptRule`
- :class:`CollapseIsinstanceChecksRule`
- :class:`ComparePrimitivesByEqualRule`
- :class:`CompareSingletonPrimitivesByIsRule`
- :class:`DeprecatedUnittestAssertsRule`
- :class:`ExplicitFrozenDataclassRule`
- :class:`NoAssertTrueForComparisonsRule`
- :class:`NoInheritFromObjectRule`
- :class:`NoNamedTupleRule`
- :class:`NoRedundantArgumentsSuperRule`
- :class:`NoRedundantFStringRule`
- :class:`NoRedundantLambdaRule`
- :class:`NoRedundantListComprehensionRule`
- :class:`NoStaticIfConditionRule`
- :class:`NoStringTypeAnnotationRule`
- :class:`ReplaceUnionWithOptionalRule`
- :class:`RewriteToComprehensionRule`
- :class:`RewriteToLiteralRule`
- :class:`SortedAttributesRule`
- :class:`UseAssertInRule`
- :class:`UseAssertIsNotNoneRule`
- :class:`UseAsyncSleepInAsyncDefRule`
- :class:`UseClassNameAsCodeRule`
- :class:`UseClsInClassmethodRule`
- :class:`UseFstringRule`
- :class:`UseLintFixmeCommentRule`
- :class:`UseTypesFromTypingRule`

.. class:: AvoidOrInExceptRule

    Discourages use of ``or`` in except clauses. If an except clause needs to catch multiple exceptions,
    they must be expressed as a parenthesized tuple, for example:
    ``except (ValueError, TypeError)``
    (https://docs.python.org/3/tutorial/errors.html#handling-exceptions)

    When ``or`` is used, only the first operand exception type of the conditional statement will be caught.
    For example::

        In [1]: class Exc1(Exception):
            ...:     pass
            ...:

        In [2]: class Exc2(Exception):
            ...:     pass
            ...:

        In [3]: try:
            ...:     raise Exception()
            ...: except Exc1 or Exc2:
            ...:     print("caught!")
            ...:
        ---------------------------------------------------------------------------
        Exception                                 Traceback (most recent call last)
        <ipython-input-3-3340d66a006c> in <module>
            1 try:
        ----> 2     raise Exception()
            3 except Exc1 or Exc2:
            4     print("caught!")
            5

        Exception:

        In [4]: try:
            ...:     raise Exc1()
            ...: except Exc1 or Exc2:
            ...:     print("caught!")
            ...:
            caught!

        In [5]: try:
            ...:     raise Exc2()
            ...: except Exc1 or Exc2:
            ...:     print("caught!")
            ...:
        ---------------------------------------------------------------------------
        Exc2                                      Traceback (most recent call last)
        <ipython-input-5-5d29c1589cc0> in <module>
            1 try:
        ----> 2     raise Exc2()
            3 except Exc1 or Exc2:
            4     print("caught!")
            5

        Exc2:

    .. attribute:: MESSAGE

        Avoid using 'or' in an except block. For example:'except ValueError or TypeError' only catches 'ValueError'. Instead, use parentheses, 'except (ValueError, TypeError)'


    .. attribute:: VALID

        .. code:: python

            try:
                print()
            except (ValueError, TypeError) as err:
                pass

    .. attribute:: INVALID

        .. code:: python

            try:
                print()
            except ValueError or TypeError:
                pass
.. class:: CollapseIsinstanceChecksRule

    The built-in ``isinstance`` function, instead of a single type,
    can take a tuple of types and check whether given target suits
    any of them. Rather than chaining multiple ``isinstance`` calls
    with a boolean-or operation, a single ``isinstance`` call where
    the second argument is a tuple of all types can be used.

    .. attribute:: MESSAGE

        Multiple isinstance calls with the same target but different types can be collapsed into a single call with a tuple of types.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            foo() or foo()
        .. code:: python

            foo(x, y) or foo(x, z)

    .. attribute:: INVALID

        .. code:: python

            isinstance(x, y) or isinstance(x, z)

            # suggested fix
            isinstance(x, (y, z))

        .. code:: python

            isinstance(x, y) or isinstance(x, z) or isinstance(x, q)

            # suggested fix
            isinstance(x, (y, z, q))

.. class:: ComparePrimitivesByEqualRule

    Enforces the use of ``==`` and ``!=`` in comparisons to primitives rather than ``is`` and ``is not``.
    The ``==`` operator checks equality (https://docs.python.org/3/reference/datamodel.html#object.__eq__),
    while ``is`` checks identity (https://docs.python.org/3/reference/expressions.html#is).

    .. attribute:: MESSAGE

        Don't use `is` or `is not` to compare primitives, as they compare references. Use == or != instead.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            a == 1
        .. code:: python

            a == '1'

    .. attribute:: INVALID

        .. code:: python

            a is 1

            # suggested fix
            a == 1

        .. code:: python

            a is '1'

            # suggested fix
            a == '1'

.. class:: CompareSingletonPrimitivesByIsRule

    Enforces the use of `is` and `is not` in comparisons to singleton primitives (None, True, False) rather than == and !=.
    The == operator checks equality, when in this scenario, we want to check identity.
    See Flake8 rules E711 (https://www.flake8rules.com/rules/E711.html) and E712 (https://www.flake8rules.com/rules/E712.html).

    .. attribute:: MESSAGE

        Comparisons to singleton primitives should not be done with == or !=, as they check equality rather than identiy. Use `is` or `is not` instead.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            if x: pass
        .. code:: python

            if not x: pass

    .. attribute:: INVALID

        .. code:: python

            x != True

            # suggested fix
            x is not True

        .. code:: python

            x != False

            # suggested fix
            x is not False

.. class:: DeprecatedUnittestAssertsRule

    Discourages the use of various deprecated unittest.TestCase functions

    See https://docs.python.org/3/library/unittest.html#deprecated-aliases

    .. attribute:: MESSAGE

        {deprecated} is deprecated, use {replacement} instead

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            self.assertEqual(a, b)
        .. code:: python

            self.assertNotEqual(a, b)

    .. attribute:: INVALID

        .. code:: python

            self.assertEquals(a, b)

            # suggested fix
            self.assertEqual(a, b)

        .. code:: python

            self.assertNotEquals(a, b)

            # suggested fix
            self.assertNotEqual(a, b)

.. class:: ExplicitFrozenDataclassRule

    Encourages the use of frozen dataclass objects by telling users to specify the
    kwarg.

    Without this lint rule, most users of dataclass won't know to use the kwarg, and
    may unintentionally end up with mutable objects.

    .. attribute:: MESSAGE

        When using dataclasses, explicitly specify a frozen keyword argument. Example: `@dataclass(frozen=True)` or `@dataclass(frozen=False)`. Docs: https://docs.python.org/3/library/dataclasses.html

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            @some_other_decorator
            class Cls: pass
        .. code:: python

            from dataclasses import dataclass
            @dataclass(frozen=False)
            class Cls: pass

    .. attribute:: INVALID

        .. code:: python

            from dataclasses import dataclass
            @some_unrelated_decorator
            @dataclass  # not called as a function
            @another_unrelated_decorator
            class Cls: pass

            # suggested fix
            from dataclasses import dataclass
            @some_unrelated_decorator
            @dataclass(frozen=True)  # not called as a function
            @another_unrelated_decorator
            class Cls: pass

        .. code:: python

            from dataclasses import dataclass
            @dataclass()  # called as a function, no kwargs
            class Cls: pass

            # suggested fix
            from dataclasses import dataclass
            @dataclass(frozen=True)  # called as a function, no kwargs
            class Cls: pass

.. class:: NoAssertTrueForComparisonsRule

    Finds incorrect use of ``assertTrue`` when the intention is to compare two values.
    These calls are replaced with ``assertEqual``.
    Comparisons with True, False and None are replaced with one-argument
    calls to ``assertTrue``, ``assertFalse`` and ``assertIsNone``.

    .. attribute:: MESSAGE

        "assertTrue" does not compare its arguments, use "assertEqual" or other appropriate functions.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            self.assertTrue(a == b)
        .. code:: python

            self.assertTrue(data.is_valid(), "is_valid() method")

    .. attribute:: INVALID

        .. code:: python

            self.assertTrue(a, 3)

            # suggested fix
            self.assertEqual(a, 3)

        .. code:: python

            self.assertTrue(hash(s[:4]), 0x1234)

            # suggested fix
            self.assertEqual(hash(s[:4]), 0x1234)

.. class:: NoInheritFromObjectRule

    In Python 3, a class is inherited from ``object`` by default.
    Explicitly inheriting from ``object`` is redundant, so removing it keeps the code simpler.

    .. attribute:: MESSAGE

        Inheriting from object is a no-op.  'class Foo:' is just fine =)

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            class A(something):    pass
        .. code:: python

            class A:
                pass

    .. attribute:: INVALID

        .. code:: python

            class B(object):
                pass

            # suggested fix
            class B:
                pass

        .. code:: python

            class B(object, A):
                pass

            # suggested fix
            class B(A):
                pass

.. class:: NoNamedTupleRule

    Enforce the use of ``dataclasses.dataclass`` decorator instead of ``NamedTuple`` for cleaner customization and
    inheritance. It supports default value, combining fields for inheritance, and omitting optional fields at
    instantiation. See `PEP 557 <https://www.python.org/dev/peps/pep-0557>`_.
    ``@dataclass`` is faster at reading an object's nested properties and executing its methods. (`benchmark <https://medium.com/@jacktator/dataclass-vs-namedtuple-vs-object-for-performance-optimization-in-python-691e234253b9>`_)

    .. attribute:: MESSAGE

        Instead of NamedTuple, consider using the @dataclass decorator from dataclasses instead for simplicity, efficiency and consistency.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            @dataclass(frozen=True)
            class Foo:
                pass
        .. code:: python

            @dataclass(frozen=False)
            class Foo:
                pass

    .. attribute:: INVALID

        .. code:: python

            from typing import NamedTuple

            class Foo(NamedTuple):
                pass

            # suggested fix
            from typing import NamedTuple

            @dataclass(frozen=True)
            class Foo:
                pass

        .. code:: python

            from typing import NamedTuple as NT

            class Foo(NT):
                pass

            # suggested fix
            from typing import NamedTuple as NT

            @dataclass(frozen=True)
            class Foo:
                pass

.. class:: NoRedundantArgumentsSuperRule

    Remove redundant arguments when using super for readability.

    .. attribute:: MESSAGE

        Do not use arguments when calling super for the parent class. See https://www.python.org/dev/peps/pep-3135/

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            class Foo(Bar):
                def foo(self, bar):
                    super().foo(bar)
        .. code:: python

            class Foo(Bar):
                def foo(self, bar):
                    super(Bar, self).foo(bar)

    .. attribute:: INVALID

        .. code:: python

            class Foo(Bar):
                def foo(self, bar):
                    super(Foo, self).foo(bar)

            # suggested fix
            class Foo(Bar):
                def foo(self, bar):
                    super().foo(bar)

        .. code:: python

            class Foo(Bar):
                @classmethod
                def foo(cls, bar):
                    super(Foo, cls).foo(bar)

            # suggested fix
            class Foo(Bar):
                @classmethod
                def foo(cls, bar):
                    super().foo(bar)

.. class:: NoRedundantFStringRule

    Remove redundant f-string without placeholders.

    .. attribute:: MESSAGE

        f-string doesn't have placeholders, remove redundant f-string.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            good: str = "good"
        .. code:: python

            good: str = f"with_arg{arg}"

    .. attribute:: INVALID

        .. code:: python

            bad: str = f"bad" + "bad"

            # suggested fix
            bad: str = "bad" + "bad"

        .. code:: python

            bad: str = f'bad'

            # suggested fix
            bad: str = 'bad'

.. class:: NoRedundantLambdaRule

    A lamba function which has a single objective of
    passing all it is arguments to another callable can
    be safely replaced by that callable.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            lambda x: foo(y)
        .. code:: python

            lambda x: foo(x, y)

    .. attribute:: INVALID

        .. code:: python

            lambda: self.func()

            # suggested fix
            self.func

        .. code:: python

            lambda x: foo(x)

            # suggested fix
            foo

.. class:: NoRedundantListComprehensionRule

    A derivative of flake8-comprehensions's C407 rule.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            any(val for val in iterable)
        .. code:: python

            all(val for val in iterable)

    .. attribute:: INVALID

        .. code:: python

            any([val for val in iterable])

            # suggested fix
            any(val for val in iterable)

        .. code:: python

            all([val for val in iterable])

            # suggested fix
            all(val for val in iterable)

.. class:: NoStaticIfConditionRule

    Discourages ``if`` conditions which evaluate to a static value (e.g. ``or True``, ``and False``, etc).

    .. attribute:: MESSAGE

        Your if condition appears to evaluate to a static value (e.g. `or True`, `and False`). Please double check this logic and if it is actually temporary debug code.


    .. attribute:: VALID

        .. code:: python

            if my_func() or not else_func():
                pass
        .. code:: python

            if function_call(True):
                pass

    .. attribute:: INVALID

        .. code:: python

            if True:
                do_something()
        .. code:: python

            if crazy_expression or True:
                do_something()
.. class:: NoStringTypeAnnotationRule

    Enforce the use of type identifier instead of using string type hints for simplicity and better syntax highlighting.
    Starting in Python 3.7, ``from __future__ import annotations`` can postpone evaluation of type annotations
    `PEP 563 <https://www.python.org/dev/peps/pep-0563/#forward-references>`_
    and thus forward references no longer need to use string annotation style.

    .. attribute:: MESSAGE

        String type hints are no longer necessary in Python, use the type identifier directly.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            from a.b import Class

            def foo() -> Class:
                return Class()
        .. code:: python

            import typing
            from a.b import Class

            def foo() -> typing.Type[Class]:
                return Class

    .. attribute:: INVALID

        .. code:: python

            from __future__ import annotations

            from a.b import Class

            def foo() -> "Class":
                return Class()

            # suggested fix
            from __future__ import annotations

            from a.b import Class

            def foo() -> Class:
                return Class()

        .. code:: python

            from __future__ import annotations

            from a.b import Class

            async def foo() -> "Class":
                return await Class()

            # suggested fix
            from __future__ import annotations

            from a.b import Class

            async def foo() -> Class:
                return await Class()

.. class:: ReplaceUnionWithOptionalRule

    Enforces the use of ``Optional[T]`` over ``Union[T, None]`` and ``Union[None, T]``.
    See https://docs.python.org/3/library/typing.html#typing.Optional to learn more about Optionals.

    .. attribute:: MESSAGE

        `Optional[T]` is preferred over `Union[T, None]` or `Union[None, T]`. Learn more: https://docs.python.org/3/library/typing.html#typing.Optional

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            def func() -> Optional[str]:
                pass
        .. code:: python

            def func() -> Optional[Dict]:
                pass

    .. attribute:: INVALID

        .. code:: python

            def func() -> Union[str, None]:
                pass
        .. code:: python

            from typing import Optional
            def func() -> Union[Dict[str, int], None]:
                pass

            # suggested fix
            from typing import Optional
            def func() -> Optional[Dict[str, int]]:
                pass

.. class:: RewriteToComprehensionRule

    A derivative of flake8-comprehensions's C400-C402 and C403-C404.
    Comprehensions are more efficient than functions calls. This C400-C402
    suggest to use `dict/set/list` comprehensions rather than respective
    function calls whenever possible. C403-C404 suggest to remove unnecessary
    list comprehension in a set/dict call, and replace it with set/dict
    comprehension.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            [val for val in iterable]
        .. code:: python

            {val for val in iterable}

    .. attribute:: INVALID

        .. code:: python

            list(val for val in iterable)

            # suggested fix
            [val for val in iterable]

        .. code:: python

            list(val for row in matrix for val in row)

            # suggested fix
            [val for row in matrix for val in row]

.. class:: RewriteToLiteralRule

    A derivative of flake8-comprehensions' C405-C406 and C409-C410. It's
    unnecessary to use a list or tuple literal within a call to tuple, list,
    set, or dict since there is literal syntax for these types.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            (1, 2)
        .. code:: python

            ()

    .. attribute:: INVALID

        .. code:: python

            tuple([1, 2])

            # suggested fix
            (1, 2)

        .. code:: python

            tuple((1, 2))

            # suggested fix
            (1, 2)

.. class:: SortedAttributesRule

    Ever wanted to sort a bunch of class attributes alphabetically?
    Well now it's easy! Just add "@sorted-attributes" in the doc string of
    a class definition and lint will automatically sort all attributes alphabetically.

    Feel free to add other methods and such -- it should only affect class attributes.

    .. attribute:: MESSAGE

        It appears you are using the @sorted-attributes directive and the class variables are unsorted. See the lint autofix suggestion.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            class MyConstants:
                """
                @sorted-attributes
                """
                A = 'zzz123'
                B = 'aaa234'

            class MyUnsortedConstants:
                B = 'aaa234'
                A = 'zzz123'

    .. attribute:: INVALID

        .. code:: python

            class MyUnsortedConstants:
                """
                @sorted-attributes
                """
                z = "hehehe"
                B = 'aaa234'
                A = 'zzz123'
                cab = "foo bar"
                Daaa = "banana"

                @classmethod
                def get_foo(cls) -> str:
                    return "some random thing"

            # suggested fix
            class MyUnsortedConstants:
                """
                @sorted-attributes
                """
                A = 'zzz123'
                B = 'aaa234'
                Daaa = "banana"
                cab = "foo bar"
                z = "hehehe"

                @classmethod
                def get_foo(cls) -> str:
                    return "some random thing"

.. class:: UseAssertInRule

    Discourages use of ``assertTrue(x in y)`` and ``assertFalse(x in y)``
    as it is deprecated (https://docs.python.org/3.8/library/unittest.html#deprecated-aliases).
    Use ``assertIn(x, y)`` and ``assertNotIn(x, y)``) instead.

    .. attribute:: MESSAGE

        Use assertIn/assertNotIn instead of assertTrue/assertFalse for inclusion check.
        See https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertIn)

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            self.assertIn(a, b)
        .. code:: python

            self.assertIn(f(), b)

    .. attribute:: INVALID

        .. code:: python

            self.assertTrue(a in b)

            # suggested fix
            self.assertIn(a, b)

        .. code:: python

            self.assertTrue(f() in b)

            # suggested fix
            self.assertIn(f(), b)

.. class:: UseAssertIsNotNoneRule

    Discourages use of ``assertTrue(x is not None)`` and ``assertFalse(x is not None)`` as it is deprecated (https://docs.python.org/3.8/library/unittest.html#deprecated-aliases).
    Use ``assertIsNotNone(x)`` and ``assertIsNone(x)``) instead.

    .. attribute:: MESSAGE

        "assertTrue" and "assertFalse" are deprecated. Use "assertIsNotNone" and "assertIsNone" instead.
        See https://docs.python.org/3.8/library/unittest.html#deprecated-aliases

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            self.assertIsNotNone(x)
        .. code:: python

            self.assertIsNone(x)

    .. attribute:: INVALID

        .. code:: python

            self.assertTrue(a is not None)

            # suggested fix
            self.assertIsNotNone(a)

        .. code:: python

            self.assertTrue(not x is None)

            # suggested fix
            self.assertIsNotNone(x)

.. class:: UseAsyncSleepInAsyncDefRule

    Detect if asyncio.sleep is used in an async function

    .. attribute:: MESSAGE

        Use asyncio.sleep in async function


    .. attribute:: VALID

        .. code:: python

            import time
            def func():
                time.sleep(1)
        .. code:: python

            from time import sleep
            def func():
                sleep(1)

    .. attribute:: INVALID

        .. code:: python

            import time
            async def func():
                time.sleep(1)
        .. code:: python

            from time import sleep
            async def func():
                sleep(1)
.. class:: UseClassNameAsCodeRule

    Meta lint rule which checks that codes of lint rules are migrated to new format in lint rule class definitions.

    .. attribute:: MESSAGE

        `IG`-series codes are deprecated. Use class name as code instead.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            MESSAGE = "This is a message"
        .. code:: python

            from fixit.common.base import CstLintRule
            class FakeRule(CstLintRule):
                MESSAGE = "This is a message"

    .. attribute:: INVALID

        .. code:: python

            MESSAGE = "IG90000 Message"

            # suggested fix
            MESSAGE = "Message"

        .. code:: python

            from fixit.common.base import CstLintRule
            class FakeRule(CstLintRule):
                INVALID = [
                    Invalid(
                        code="",
                        kind="IG000"
                    )
                ]

            # suggested fix
            from fixit.common.base import CstLintRule
            class FakeRule(CstLintRule):
                INVALID = [
                    Invalid(
                        code="",
                        )
                ]

.. class:: UseClsInClassmethodRule

    Enforces using ``cls`` as the first argument in a ``@classmethod``.

    .. attribute:: MESSAGE

        When using @classmethod, the first argument must be `cls`.

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            class foo:
                # classmethod with cls first arg.
                @classmethod
                def cm(cls, a, b, c):
                    pass
        .. code:: python

            class foo:
                # non-classmethod with non-cls first arg.
                def nm(self, a, b, c):
                    pass

    .. attribute:: INVALID

        .. code:: python

            class foo:
                # No args at all.
                @classmethod
                def cm():
                    pass

            # suggested fix
            class foo:
                # No args at all.
                @classmethod
                def cm(cls):
                    pass

        .. code:: python

            class foo:
                # Single arg + reference.
                @classmethod
                def cm(a):
                    return a

            # suggested fix
            class foo:
                # Single arg + reference.
                @classmethod
                def cm(cls):
                    return cls

.. class:: UseFstringRule

    Encourages the use of f-string instead of %-formatting or .format() for high code quality and efficiency.

    Following two cases not covered:

    1. arguments length greater than 30 characters: for better readibility reason
        For example:

        1: this is the answer: %d" % (a_long_function_call() + b_another_long_function_call())
        2: f"this is the answer: {a_long_function_call() + b_another_long_function_call()}"
        3: result = a_long_function_call() + b_another_long_function_call()
        f"this is the answer: {result}"

        Line 1 is more readable than line 2. Ideally, we'd like developers to manually fix this case to line 3

    2. only %s placeholders are linted against for now. We leave it as future work to support other placeholders.
        For example, %d raises TypeError for non-numeric objects, whereas f"{x:d}" raises ValueError.
        This discrepancy in the type of exception raised could potentially break the logic in the code where the exception is handled

    .. attribute:: MESSAGE

        Do not use printf style formatting or .format(). Use f-string instead to be more readable and efficient. See https://www.python.org/dev/peps/pep-0498/

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            somebody='you'; f"Hey, {somebody}."
        .. code:: python

            "hey"

    .. attribute:: INVALID

        .. code:: python

            "Hey, {somebody}.".format(somebody="you")
        .. code:: python

            "%s" % "hi"

            # suggested fix
            f"{'hi'}"

.. class:: UseLintFixmeCommentRule

    To silence a lint warning, use ``lint-fixme`` (when plans to fix the issue later) or ``lint-ignore``
    (when the lint warning is not valid) comments.
    The comment requires to be in a standalone comment line and follows the format ``lint-fixme: RULE_NAMES EXTRA_COMMENTS``.
    It suppresses the lint warning with the RULE_NAMES in the next line.
    RULE_NAMES can be one or more lint rule names separated by comma.
    ``noqa`` is deprecated and not supported because explicitly providing lint rule names to be suppressed
    in lint-fixme comment is preferred over implicit noqa comments. Implicit noqa suppression comments
    sometimes accidentally silence warnings unexpectedly.

    .. attribute:: MESSAGE

        noqa is deprecated. Use `lint-fixme` or `lint-ignore` instead.


    .. attribute:: VALID

        .. code:: python

            # lint-fixme: UseFstringRule
            "%s" % "hi"
        .. code:: python

            # lint-ignore: UsePlusForStringConcatRule
            'ab' 'cd'

    .. attribute:: INVALID

        .. code:: python

            fn() # noqa
        .. code:: python

            (
             1,
             2,  # noqa
            )
.. class:: UseTypesFromTypingRule

    Enforces the use of types from the ``typing`` module in type annotations in place
    of ``builtins.{builtin_type}`` since the type system doesn't recognize the latter
    as a valid type before Python ``3.10``.

    .. attribute:: AUTOFIX
        :type: Yes

    .. attribute:: PYTHON_VERSION
        :type: '< 3.10'

    .. attribute:: VALID

        .. code:: python

            def fuction(list: List[str]) -> None:
                pass
        .. code:: python

            def function() -> None:
                thing: Dict[str, str] = {}

    .. attribute:: INVALID

        .. code:: python

            from typing import List
            def whatever(list: list[str]) -> None:
                pass

            # suggested fix
            from typing import List
            def whatever(list: List[str]) -> None:
                pass

        .. code:: python

            def function(list: list[str]) -> None:
                pass

``fixit.upgrade``
^^^^^^^^^^^^^^^^^

.. automodule:: fixit.upgrade

- :class:`FixitDeprecatedImport`

.. class:: FixitDeprecatedImport

    Upgrade lint rules to replace deprecated imports with their replacements.

    .. attribute:: MESSAGE

        Fixit deprecated import {old_name}, use {new_name} instead

    .. attribute:: AUTOFIX
        :type: Yes


    .. attribute:: VALID

        .. code:: python

            from fixit import LintRule
        .. code:: python

            from fixit import Invalid

    .. attribute:: INVALID

        .. code:: python

            from fixit import CstLintRule

            # suggested fix
            from fixit import LintRule

        .. code:: python

            from fixit import CSTLintRule

            # suggested fix
            from fixit import LintRule

    