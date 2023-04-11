.. _commands:

Commands
--------

``lint``
^^^^^^^^

Lint one or more paths, and print a list of lint errors.

.. code:: console

    $ fixit lint [--diff] [PATH ...]

.. attribute:: --diff / -d

    Show suggested fixes, in unified diff format, when available.


``fix``
^^^^^^^

Lint one or more paths, and apply suggested fixes.

.. code:: console

    $ fixit fix [--interactive | --automatic [--diff]] [PATH ...]

.. attribute:: --interactive / -i
    
    Interactively prompt the user to apply or decline suggested fixes for
    each auto-fix available. *default*

.. attribute:: --automatic / -a

    Automatically apply suggested fixes for all lint errors when available.

.. attribute:: --diff / -d

    Show applied fixes in unified diff format when applied automatically.


``test``
^^^^^^^^

Test one or more lint rules using their :attr:`~fixit.LintRule.VALID` and
:attr:`~fixit.LintRule.INVALID` test cases.

Expects qualified lint rule packages or names, with the same form as when
configuring :attr:`enable` and :attr:`disable`.

.. code:: console

    $ fixit test [RULES ...]

Example:

.. code:: console

    $ fixit test .examples.teambread.rules
    test_INVALID_0 (fixit.testing.HollywoodNameRule) ... ok
    test_INVALID_1 (fixit.testing.HollywoodNameRule) ... ok
    test_VALID_0 (fixit.testing.HollywoodNameRule) ... ok
    test_VALID_1 (fixit.testing.HollywoodNameRule) ... ok

    ----------------------------------------------------------------------
    Ran 4 tests in 0.024s

    OK


``debug``
^^^^^^^^^

Debug options for validating Fixit configuration.

.. code:: console

    $ fixit debug [PATH ...]
