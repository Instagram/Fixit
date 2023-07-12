Upgrading
=========

Fixit 2.0 features a foundational rewrite of the linting engine, but retains
many of the key concepts from Fixit 1 (version ``0.1.4``), and includes tools
to help users make the jump to the latest version.

This page will attempt to concisely cover major changes between the versions.
See the :ref:`User Guide <user-guide>` for a full
:ref:`command reference <Commands>`, `configuration format <Configuration>`_,
and `quick start <Quick Start>`_.


Configuration
-------------

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
    implementations can be built, but discovery is not yet defined.

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

- ``use_noqa``
    Fixit 2 drops support for running Flake8 rules within Fixit, and does not
    support Flake8-style suppressions via ``# noqa`` directives.

    See :ref:`suppressions` for supported lint suppression directives.


Commands
--------

The following CLI commands from previous versions are roughly equivalent:

- ``python -m fixit.cli.run_rules [--rules ...] <path>``

    .. code-block:: shell-session

        $ fixit lint [--rules ...] <path>

- ``python -m fixit.cli.apply_fix [--rules ...] <path>``

    .. code-block:: shell-session

        $ fixit fix [--rules ...] <path>

See the full :ref:`Commands` list for details.


Lint Rules
----------


Many classes from Fixit 1 have been renamed to be more concise, and reduce the
need for ``import LongName as Short``  style imports:

- ``fixit.CstLintRule`` -> :class:`~fixit.LintRule`
- ``fixit.ValidTestCase`` -> :class:`~fixit.Valid`