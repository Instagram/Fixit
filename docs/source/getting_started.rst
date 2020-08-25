===============
Getting Started
===============

Now that you have installed the Fixit package, the next step towards integrating it into your repository
is to create a config file.


Configuration File
==================

1. To initialize a configuration file populated with some defaults, run::

    python -m fixit.common.cli.init_config

This will create a ``.fixit.config.yaml`` with default settings in the current working directory.

2. Next, you may want to edit or add some specific settings. The available configurations are:

- ``block_list_patterns``: A list of patterns that indicate that a file should not be linted. For example::

    block_list_patterns: ['@generated', '@nolint']

will tell Fixit to skip linting any files that have ``@generated`` or ``@nolint`` in their contents.

- ``block_list_rules``: A list of rules (whether custom or from Fixit) that should not be applied to the repository. For example::

    block_list_rules: [NoInheritFromObjectRule]

- ``fixture_dir``: The directory in which fixture files required for unit testing are to be found. This is only necessary if you are testing rules that use a metadata cache (see :ref:`AwaitAsyncCallRule` for an example of such a rule). This can be an absolute path, or a path relative to `repo_root` (see below).
- ``formatter``: A list of the formatter commands to use after a lint is complete. These will be passed to the ``args`` parameter in `subprocess.check_output <https://docs.python.org/3.8/library/subprocess.html#subprocess.check_output>`_ in the order in which they appear. For example::

    formatter: [black, '-']

Here, the formatter of choice would be `Black <https://black.readthedocs.io/en/stable/>`_ and the added ``-`` tells it to read from standard input, and write to standard output so that it is compatible with Fixit's formatting logic.

- ``packages``: The Python packages in which to search for lint rules. For example::

    packages: [fixit.rules, my.custom.package]

- ``repo_root``: The path to the repository root. This can be a path relative to the `.fixit.config.yaml` file or an absolute path. For example::

    repo_root: .

- ``rule_config``: Rule-specific configurations. For example::

    ImportConstraintsRule:
        fixit:
            rules: [["*", "allow"]]

(see :ref:`ImportConstraintsRule` for more details on this example)

3. A `.fixit.config.yaml` example with populated settings::

    block_list_patterns:
    - '@generated'
    - '@nolint'
    block_list_rules:
    - BlockListedRule
    fixture_dir: ./tests/fixtures
    formatter:
    - black
    - '-'
    packages:
    - fixit.rules
    repo_root: .
    rule_config:
        ImportConstraintsRule:
            fixit:
                rules: [["*", "allow"]]


Enforcing Custom Rules
======================

After finishing up the configuration, you may want to enforce some custom lint rules in your repository.

1. Start by creating a directory where your custom rules will live. Make sure to include an ``__init__.py`` file so that the directory is importable as a package.
This can simply be an empty file. For example::

    my_repo_root
        └── lint
            └── custom_rules
                └── __init__.py

2. Include the dotted name of the package in the `.fixit.config.yaml` file under the `packages` setting::

    packages:
    - fixit.rules
    - lint.custom_rules

3. See the :doc:`Build a Lint Rule <build_a_lint_rule>` page for more details on how to write the logic for a custom lint rule.
