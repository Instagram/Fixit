FP2: Local Lint Rules
=====================

By default, Fixit expects rules to be referenced by their fully-qualified
module and/or class name. For example, ``fixit.rules`` refers to the bundled set
if lint rules shipped with Fixit. Third party rules available in the environment
can similarly be referenced by their module name, as long as they are installed
and importable by Fixit at runtime.

However, in many cases, it is also useful for projects using Fixit to build
custom lint rules specific to the project being linted. It is beneficial for
those rules to be defined within the codebase being linted, without needing to
first install those lint rules into the environment before running Fixit.

These are defined as "local rules", and will require dedicated behavior from
Fixit to discover and import these rules at runtime, as well as special
configuration syntax for enabling these local rules in a project.


Configuration
-------------

When configuring the set of enabled or disabled rules, any local rules must
be marked with a single leading period, and referred to using their path
relative to the configuration file's directory.

For example, a configuration file at ``project/fixit.toml`` could include
rules defined in ``project/some/local/rules.py`` with the following:

.. code-block:: toml

    [tool.fixit]
    enable = [".some.local.rules"]


Limitations
-----------

For simplicity of implementation, it makes sense to disallow local rules from
outside of the configuration file's parent directory. In other words,
``project/subdir/fixit.toml`` can not reference local rules from
``project/other/rules.py``.

To apply rules from a different subdirectory to another subdirectory,
a configuration located in a common parent can use
:ref:`configuration overrides <overrides>`.
For instance, ``project/fixit.toml`` could specify an override for the
``subdir`` path to enable ``".local.rules"``.
