FP2: Local Lint Rules
=====================

By default, Fixit expects rules to be referenced by their fully-qualified
module and/or class name. For example, ``fixit.rules`` refers to the bundled set
if lint rules shipped with Fixit. Third party rules available in the environment
can similarly be referenced by their module name, as long as they are installed
and importable by Fixit at runtime. These will be collectively referred to as
"global rules" here for sake of clarity.

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


References to local rules should be accepted in either ``enable`` or ``disable``
options, including overrides, to provide the same selection criteria available
to global rules:

.. code-block:: toml

    [tool.fixit]
    enable = [".rules"]

    [[tool.fixit.overrides]]
    path = "project1"
    disable = [".rules.PickyRule"]
    enable = [".project1.rules"]


Implementation
--------------

When gathering enabled/disabled rules from configuration, Fixit currently
just records the module name (fqdn) and does set operations when merging
configs/overrides. In order to differentiate and manage local rules correctly,
without affecting the behavior of merging/overrides, one possible option is to
replace the simple string with a tuple of path and module.

For example, where a global rule would be tracked as just ``"fixit.rules"``,
local rules from ``foo/bar/fixit.toml`` could be tracked as
``(Path('foo/bar'), ".local.rules"))``, allowing set operations while still
tracking their origin, and preventing collisions from different directories.

In this implementation, the path object should match the parent directory
containing the configuration file that enables or disables these local rules.
Options in both a ``pyproject.toml`` and ``fixit.toml`` from the same exact
directory would use the same path object, as would any local rules referenced
by overrides in those files.

---

When discovering and loading rules, the system should attempt to make sure
that it is loading rules from the local path, rather than accidentally loading
rules from the outside environment. This can be done either by a temporarily
restricted path when importing, or with a custom import loader.

The former may be a simpler starting point, and can be handled with a temporary
override of ``sys.path`` to include the local directory — and nothing else? —
and then importing the module as normal, with the leading period removed.

This could look something like:

.. code-block:: python

    with temporary_sys_path(parent_path):
        name = name.lstrip(".")
        module = importlib.import_module(name)
 
Once loaded, local modules and rules can be handled and traversed the same as
for global rules, though the logic for filtering out disabled local rules may
require more nuance.


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

----

Also for simplicity of implementation (and explanation to users), it makes
sense to disallow filtering of local rules from outside the file (or exact
parent directory) that originally enabled them.

For example, this would be considered invalid, or at least would not
accomplish what the user may expect:

.. code-block:: toml

    # foo/fixit.toml

    [tool.fixit]
    enable = [".local.rules"]

.. code-block:: toml

    # foo/bar/fixit.toml

    [tool.fixit]
    disable = [".local.rules"]

Rather, the expected way to make this work would be with subpath overrides
in the parent directory's ``fixit.toml`` file:

.. code-block:: toml

    # foo/fixit.toml

    [tool.fixit]
    enable = [".local.rules"]

    [[tool.fixit.overrides]]
    path = "bar"
    disable = [".local.rules"]
