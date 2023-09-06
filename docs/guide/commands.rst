.. _commands:

Commands
--------

.. code:: console

    $ fixit [OPTIONS] COMMAND ...


The following options are available for all commands:

.. attribute:: --debug / --quiet

    Raise or lower the level of output and logging.

.. attribute:: --config-file PATH

    Override the normal hierarchical configuration and use the configuration
    from the specified path, ignoring all other configuration files entirely.

.. attribute:: --tags TAGS

    Select or filter the set of lint rules to apply based on their tags.

    Takes a comma-separated list of tag names, optionally prefixed with ``!``,
    ``^``, or ``-``. Tags without one of those prefixes will be considered
    "include" tags, while tags with one of those prefixes will be considered
    "exclude" tags.

    Lint rules will be enabled if and only if they have at least one tag that
    in the "include" list, and no tags in the "exclude" list.

    For example:

    .. code:: console

        $ fixit --tags "hello, world, ^cats" ...

    The command above will filter the set of enabled lint rules to ones that
    have either the "hello" or "world" tags, and exclude any rules with the
    "cats" tag, even if they would have otherwise been selected by the other
    two tags.


``lint``
^^^^^^^^

Lint one or more paths, and print a list of lint errors. If "-" is given as the
first path, then the second given path will be used for configuration lookup
and error messages, and the input read from STDIN.

.. code:: console

    $ fixit lint [--diff] [PATH ...]

.. attribute:: --diff / -d

    Show suggested fixes, in unified diff format, when available.


``fix``
^^^^^^^

Lint one or more paths, and apply suggested fixes. If "-" is given as the
first path, then the second given path will be used for configuration lookup,
the input read from STDIN, and the fixed output printed to STDOUT (ignoring
:attr:`--interactive`).

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


``upgrade``
^^^^^^^^^^^

Upgrade lint rules or client code to the latest version of Fixit.
Automatically applies fixes from all upgrade rules in :mod:`fixit.upgrade`.

Shortcut for ``fixit --rules fixit.upgrade fix --automatic <path>``

.. code:: console

    $ fixit upgrade [PATH ...]


``debug``
^^^^^^^^^

Debug options for validating Fixit configuration.

.. code:: console

    $ fixit debug [PATH ...]
