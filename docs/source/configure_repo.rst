===============
Getting Started
===============

Now that you have installed the Fixit package, the next step to getting started with
building custom lint rules using is to create a config file.


Configuration File
==================

1. Create a file at the root of your repository, and name it `fixit.config.yaml`.

2. Next, you will want to configure some specific settings. The available configurations are

- `block_list_patterns`: A list of patterns that indicate when a file should not be linted. For example: `[@generated]`
- `block_list_rules`: A list of rules (whether custom or from Fixit) that should not be applied to the repository.
- `fixture_dir`: The directory in which fixtures files required for unit testing are to be found. This is only necessary if you are testing rules that use a metadata cache (see :ref:`rules:AwaitAsyncCallRule` for an example of such a rule). This can be an absolute path, or a path relative to `repo_root` (see below).
- `formatter`: A list of the formatter commands to use after a lint is complete. For example: `[black, -]`
- `packages`: The Python packages in which to search for lint rules. For example: `[fixit.rules, my.custom.package]`
- `repo_root`: The path to the repository root. This can be a relative path (e.g. `.`), or an absolute path.
- `rule_config`: Rule-specific configurations. For example:
.. code-block::
[
    ImportConstraintsRule:
        fixit:
            rules: [["*", "allow"]]
]
(see :ref:`ImportConstraintsRule` for more details about this example)
