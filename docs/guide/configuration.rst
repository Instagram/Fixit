.. _configuration:

Configuration
-------------

Fixit uses `TOML format <https://toml.io>`_ for configuration, and supports
hierarchical, cascading configuration. Fixit will read values from both the
standardized ``pyproject.toml`` file as well as a separate ``.fixit.toml`` or
``fixit.toml`` file, with values from the latter taking precendence over the
former, and values from files "nearer" to those being linted taking precedence
over values from files "further" away.

When determining the configuration to use for a given path, Fixit will continue
looking upward in the filesystem until it reaches either the root of the
filesystem, or a configuration file is found with :attr:`root` set to ``True``.
Fixit will then read configuration values from each file, from further to
nearest, and merge or override values as appropriate.

This behavior enables a monorepo to provide a baseline configuration, while
individual projects can choose to either add to that baseline, or define their
own root of configuration to ignore any other baseline configs. This also allows
the inclusion of external or third-party projects to maintain consistent linting
results, regardless of whether they are being linted externally or within the
containing monorepo.


``[tool.fixit]``
^^^^^^^^^^^^^^^^

The main configuration table.

.. attribute:: root
    :type: bool
    :value: False

    Marks this file as a root of the configuration hierarchy.

    If set to ``True``, Fixit will not visit any files further up the hierarchy.

.. attribute:: enable
    :type: list[str]
    :value: []

    List of modules or individual rules to enable when linting files covered
    by this configuration.

    Rules bundled with Fixit, or available in the environment's site-packages,
    can be referenced as a group by their fully-qualified package name, or
    individually by adding a colon and the rule name:

    .. code-block:: toml

        enable = [
            "fixit.rules",  # all lint rules in this package (non-recursive)
            "fixit.rules:UseFstringRule",  # single lint rule by name
        ]

    Local rules, available only in the repo being linted, can be referenced by
    their locally-qualified package names, as if they were being imported from
    a Python module *relative to the configuration file specifying the rule*:

    .. code-block:: toml

        # teambread/fixit.toml
        enable = [
            ".rules",  # all rules in teambread/rules/ (non-recursive)
            ".rules.hollywood",  # all rules in teambread/rules/hollywood.py
            ".rules:HollywoodNameRule",  # single lint rule by name
        ]

    Overrides disabled rules from any configuration further up the hierarchy.

    Fixit will enable the built-in :mod:`fixit.rules` lint rules by default.

.. attribute:: disable
    :type: list[str]
    :value: []

    List of modules or individual rules to disable when linting files covered
    by this configuration.

    Overrides enabled rules from this file, as well any configuration files
    further up the hierarchy.

    See :attr:`enable` for details on referencing lint rules.

.. attribute:: python-version
    :type: str
    :value: "3.10"

    Python version to target when selecting lint rules. Rules with
    :attr:`~fixit.LintRule.PYTHON_VERSION` specifiers that don't match this
    target version will be automatically disabled during linting.
    
    Defaults to the currently active version of Python.
    Set to empty string ``""`` to disable target version checking.


``[tool.fixit.options]``
^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``options`` table allows setting options for individual lint rules,
by mapping the fully-qualified rule name to a dictionary of key/value pairs:

.. code-block:: toml

    [tool.fixit.options]
    "fixit.rules:ExampleRule" = {greeting = "hello world"}

Alternatively, for rules with a large number of options, the rule name can
be included in the table name for easier usage. Note that the quotes in the
table name are required for correctly specifying options:

.. code-block:: toml

    [tool.fixit.options."fixit.rules:ExampleRule"]
    greeting = "hello world"
    answer = 42


.. _overrides:

``[[tool.fixit.overrides]]``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Overrides provide a mechanism for hierarchical configuration within a single
configuration file. They are defined as an
`array of tables <https://toml.io/en/v1.0.0#array-of-tables>`_, with each table
defining the subpath it applies to, along with any values from the tables above:

.. code-block:: toml

    [[tool.fixit.overrides]]
    path = "foo/bar"
    disable = ["fixit.rules:ExampleRule"]

    [[tool.fixit.overrides.options]]
    # applies to the above override path only
    "fixit.rules:Story" = {closing = "goodnight moon"}

    [[tool.fixit.overrides]]
    path = "fizz/buzz"
    enable = ["plugin:SomethingNeat"]
