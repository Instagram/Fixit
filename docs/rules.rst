
.. module:: fixit.rules

Builtin Rules
-------------

These rules are all part of the :mod:`fixit.rules` package, and are enabled by default
unless explicitly listed in the :attr:`disable` configuration option.

- :class:`AvoidOrInExceptRule`
- :class:`CollapseIsinstanceChecksRule`
- :class:`ComparePrimitivesByEqualRule`
- :class:`CompareSingletonPrimitivesByIsRule`
- :class:`ExplicitFrozenDataclassRule`
- :class:`NoAssertEqualsRule`
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
    

.. class:: CollapseIsinstanceChecksRule

    The built-in ``isinstance`` function, instead of a single type,
    can take a tuple of types and check whether given target suits
    any of them. Rather than chaining multiple ``isinstance`` calls
    with a boolean-or operation, a single ``isinstance`` call where
    the second argument is a tuple of all types can be used.
    

.. class:: ComparePrimitivesByEqualRule

    Enforces the use of ``==`` and ``!=`` in comparisons to primitives rather than ``is`` and ``is not``.
    The ``==`` operator checks equality (https://docs.python.org/3/reference/datamodel.html#object.__eq__),
    while ``is`` checks identity (https://docs.python.org/3/reference/expressions.html#is).
    

.. class:: CompareSingletonPrimitivesByIsRule

    Enforces the use of `is` and `is not` in comparisons to singleton primitives (None, True, False) rather than == and !=.
    The == operator checks equality, when in this scenario, we want to check identity.
    See Flake8 rules E711 (https://www.flake8rules.com/rules/E711.html) and E712 (https://www.flake8rules.com/rules/E712.html).
    

.. class:: ExplicitFrozenDataclassRule

    Encourages the use of frozen dataclass objects by telling users to specify the
    kwarg.

    Without this lint rule, most users of dataclass won't know to use the kwarg, and
    may unintentionally end up with mutable objects.
    

.. class:: NoAssertEqualsRule

    Discourages use of ``assertEquals`` as it is deprecated (see https://docs.python.org/2/library/unittest.html#deprecated-aliases
    and https://bugs.python.org/issue9424). Use the standardized ``assertEqual`` instead.
    

.. class:: NoAssertTrueForComparisonsRule

    Finds incorrect use of ``assertTrue`` when the intention is to compare two values.
    These calls are replaced with ``assertEqual``.
    Comparisons with True, False and None are replaced with one-argument
    calls to ``assertTrue``, ``assertFalse`` and ``assertIsNone``.
    

.. class:: NoInheritFromObjectRule

    In Python 3, a class is inherited from ``object`` by default.
    Explicitly inheriting from ``object`` is redundant, so removing it keeps the code simpler.
    

.. class:: NoNamedTupleRule

    Enforce the use of ``dataclasses.dataclass`` decorator instead of ``NamedTuple`` for cleaner customization and
    inheritance. It supports default value, combining fields for inheritance, and omitting optional fields at
    instantiation. See `PEP 557 <https://www.python.org/dev/peps/pep-0557>`_.
    ``@dataclass`` is faster at reading an object's nested properties and executing its methods. (`benchmark <https://medium.com/@jacktator/dataclass-vs-namedtuple-vs-object-for-performance-optimization-in-python-691e234253b9>`_)
    

.. class:: NoRedundantArgumentsSuperRule

    Remove redundant arguments when using super for readability.
    

.. class:: NoRedundantFStringRule

    Remove redundant f-string without placeholders.
    

.. class:: NoRedundantLambdaRule

    A lamba function which has a single objective of
    passing all it is arguments to another callable can
    be safely replaced by that callable.
    

.. class:: NoRedundantListComprehensionRule

    A derivative of flake8-comprehensions's C407 rule.
    

.. class:: NoStaticIfConditionRule

    Discourages ``if`` conditions which evaluate to a static value (e.g. ``or True``, ``and False``, etc).
    

.. class:: NoStringTypeAnnotationRule

    Enforce the use of type identifier instead of using string type hints for simplicity and better syntax highlighting.
    Starting in Python 3.7, ``from __future__ import annotations`` can postpone evaluation of type annotations
    `PEP 563 <https://www.python.org/dev/peps/pep-0563/#forward-references>`_
    and thus forward references no longer need to use string annotation style.
    

.. class:: ReplaceUnionWithOptionalRule

    Enforces the use of ``Optional[T]`` over ``Union[T, None]`` and ``Union[None, T]``.
    See https://docs.python.org/3/library/typing.html#typing.Optional to learn more about Optionals.
    

.. class:: RewriteToComprehensionRule

    A derivative of flake8-comprehensions's C400-C402 and C403-C404.
    Comprehensions are more efficient than functions calls. This C400-C402
    suggest to use `dict/set/list` comprehensions rather than respective
    function calls whenever possible. C403-C404 suggest to remove unnecessary
    list comprehension in a set/dict call, and replace it with set/dict
    comprehension.
    

.. class:: RewriteToLiteralRule

    A derivative of flake8-comprehensions' C405-C406 and C409-C410. It's
    unnecessary to use a list or tuple literal within a call to tuple, list,
    set, or dict since there is literal syntax for these types.
    

.. class:: SortedAttributesRule

    Ever wanted to sort a bunch of class attributes alphabetically?
    Well now it's easy! Just add "@sorted-attributes" in the doc string of
    a class definition and lint will automatically sort all attributes alphabetically.

    Feel free to add other methods and such -- it should only affect class attributes.
    

.. class:: UseAssertInRule

    Discourages use of ``assertTrue(x in y)`` and ``assertFalse(x in y)``
    as it is deprecated (https://docs.python.org/3.8/library/unittest.html#deprecated-aliases).
    Use ``assertIn(x, y)`` and ``assertNotIn(x, y)``) instead.
    

.. class:: UseAssertIsNotNoneRule

    Discourages use of ``assertTrue(x is not None)`` and ``assertFalse(x is not None)`` as it is deprecated (https://docs.python.org/3.8/library/unittest.html#deprecated-aliases).
    Use ``assertIsNotNone(x)`` and ``assertIsNone(x)``) instead.

    

.. class:: UseClassNameAsCodeRule

    Meta lint rule which checks that codes of lint rules are migrated to new format in lint rule class definitions.
    

.. class:: UseClsInClassmethodRule

    Enforces using ``cls`` as the first argument in a ``@classmethod``.
    

.. class:: UseFstringRule

    Encourages the use of f-string instead of %-formatting or .format() for high code quality and efficiency.

    Following two cases not covered:

    1. arguments length greater than 30 characters: for better readibility reason
        For example:

        1: this is the answer: %d" % (a_long_function_call() + b_another_long_function_call())
        2: f"this is the answer: {a_long_function_call() + b_another_long_function_call()}"
        3: result = a_long_function_call() + b_another_long_function_call()
        f"this is the answer: {result}"

        Line 1 is more readable than line 2. Ideally, we’d like developers to manually fix this case to line 3

    2. only %s placeholders are linted against for now. We leave it as future work to support other placeholders.
        For example, %d raises TypeError for non-numeric objects, whereas f“{x:d}” raises ValueError.
        This discrepancy in the type of exception raised could potentially break the logic in the code where the exception is handled
    

.. class:: UseLintFixmeCommentRule

    To silence a lint warning, use ``lint-fixme`` (when plans to fix the issue later) or ``lint-ignore``
    (when the lint warning is not valid) comments.
    The comment requires to be in a standalone comment line and follows the format ``lint-fixme: RULE_NAMES EXTRA_COMMENTS``.
    It suppresses the lint warning with the RULE_NAMES in the next line.
    RULE_NAMES can be one or more lint rule names separated by comma.
    ``noqa`` is deprecated and not supported because explicitly providing lint rule names to be suppressed
    in lint-fixme comment is preferred over implicit noqa comments. Implicit noqa suppression comments
    sometimes accidentally silence warnings unexpectedly.
    

.. class:: UseTypesFromTypingRule

    Enforces the use of types from the ``typing`` module in type annotations in place of ``builtins.{builtin_type}``
    since the type system doesn't recognize the latter as a valid type.
    

    