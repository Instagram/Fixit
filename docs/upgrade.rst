.. _upgrade:

Upgrading
=========

Fixit includes a command to perform automatic upgrades of lint rules and other
client code for compatibility with the latest version of Fixit.
This command will apply simple renames and structure changes where possible:

.. code-block:: shell-session

    $ fixit upgrade <path>

Once lint rules have been upgraded, they can be tested against their defined
valid/invalid test cases, using their fully qualified package and/or rule name:

.. code-block:: shell-session

    $ fixit test "mypackage.rules"

Details about upgrades and changes from old releases can be found below,
including any changes now covered by the automated upgrade tools.

This page will attempt to concisely cover major changes between the versions.
See the :ref:`user-guide`, :ref:`api`, and :ref:`changelog` for more
information about the latest version.


From Fixit 1 (v0.1.x)
---------------------

Fixit 2.0 features a foundational rewrite of the linting engine, configuration
system, CLI commands, and more.


Configuration
^^^^^^^^^^^^^

Fixit 2 uses `TOML <https://toml.io>`_ format for configuration, as opposed to
the YAML format from previous versions. Configuration options can now be
located in either the standard ``pyproject.toml`` file, or a dedicated
``fixit.toml`` file.

Most options can be migrated to the new format as such:

- ``allow_list_rules`` / ``block_list_rules`` / ``packages``:

    Rules are now referenced by fully qualified package name, with an optional
    rule name, via the :attr:`enable` and :attr:`disable` options.
    It is no longer required to specify the ``packages`` list separately, and
    omitting a rule name will automatically all rules from the given package:

    .. code-block:: yaml

        allow_list_rules: [CustomLintRule]
        packages: [mypackage.rules]

    .. code-block:: toml

        enable = [
            "mypackage.rules:CustomLintRule",  # single rule
            "mypackage.rules",  # all rules from package
        ]

    Built-in lint rules are mostly unchanged, though most of them no longer
    contain the ``Rule`` suffix. See the :ref:`builtin-rules` for a full list
    of rules included with Fixit.

    Note that all built-in rules are enabled by default.

- ``formatter``:

    Files can be formatted after linting, using one of the supported formatters,
    with the :attr:`formatter` option:

    .. code-block:: toml

        formatter = "ufmt"  # or "black"

    Using arbitrary formatters via subprocess commands and stdin/stdout
    is no longer supported. Alternative :class:`~fixit.Formatter`
    implementations can be built, but a discovery mechanism is not yet defined.

- ``repo_root``:

    The repository or project root is inferred based on the furthest location
    of a ``pyproject.toml`` or ``fixit.toml`` file, or explicitly by the nearest
    configuration file with the :attr:`root` option set.

- ``rule_config``:

    Rule specific configuration is now specified in the
    :ref:`options <rule-options>` table, using the fully qualified rule name
    similar to :attr:`enable` and :attr:`disable`:

    .. code-block:: yaml

        rule_config:
            CustomLintRule:
                key: value

    .. code-block:: toml

        [tool.fixit.options]
        "mypackage.rules:CustomLintRule" = {key = "value"}


The following options are no longer supported:

- ``block_list_patterns``:

    An alternative option may be available in the future.
    See `issue #354 <https://github.com/Instagram/Fixit/issues/354>`_.

- ``fixture_dir``

    There is no expected use case for this option in Fixit 2.

- ``use_noqa``

    Fixit 2 drops support for running Flake8 as part of Fixit, and does not
    support Flake8-style suppressions via ``# noqa`` directives.

    See :ref:`suppressions` for supported lint suppression directives.


API
^^^

Lint rules written for Fixit 1 need some minor structural changes to work with
Fixit 2, and a number of core types have been renamed to be more concise, and
reduce the need for ``import LongName as Short``  style imports.

Renames
%%%%%%%

These types have been renamed, but have temporary aliases that will be removed
in a future release:

- ``fixit.CstLintRule`` → :class:`fixit.LintRule`
- ``fixit.ValidTestCase`` → :class:`fixit.Valid`
- ``fixit.InvalidTestCase`` → :class:`fixit.Invalid`

All renames should be automatically upgraded with the ``fixit upgrade`` command.

Changes
%%%%%%%

- :class:`fixit.Invalid`:

    This type now takes an optional :class:`~libcst.CodeRange` instead of line
    and column indexes. The ``config``, ``filename``, and ``kind`` parameters
    have been removed.

- :class:`fixit.Valid`:

    The ``config`` and ``filename`` parameters have been removed.


Removals
%%%%%%%%

- ``fixit.LintConfig``

    This type has been replaced with the new :class:`fixit.Config` type that
    represents the merged configuration options matching a specific path.

- ``fixit.CstContext``

    This type has been removed. The current filename can be retrieved using
    the :class:`~libcst.metadata.FilePathProvider` metadata with the top-level
    :class:`~libcst.Module` object.

Commands
^^^^^^^^

The following CLI commands from previous versions are roughly equivalent:

- ``python -m fixit.cli.run_rules [--rules ...] <path>``

    .. code-block:: shell-session

        $ fixit lint [--rules ...] <path>

- ``python -m fixit.cli.apply_fix [--rules ...] <path>``

    .. code-block:: shell-session

        $ fixit fix [--rules ...] <path>

See the full :ref:`Commands` list for details.
