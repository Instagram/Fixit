Quick Start
-----------


Setup
^^^^^

Install Fixit from PyPI:

.. code-block:: console

    $ pip install --pre "fixit >1"

By default, Fixit enables all of the lint rules that ship with Fixit,
all of which are part of the :mod:`fixit.rules` package.

If you want to customize the list of enabled rules, either to add new rules
or disable others, see the :ref:`Configuration Guide <configuration>` for
details and options available.

Fixit offers multiple integrations, including pre-commit actions and LSP support
for VSCode and other editors. See the :ref:`Integrations Guide <integrations>`
for details.

If you are upgrading from previous versions of Fixit, look at the
:ref:`Upgrade Guide <upgrade>` for a list of changes and tools to assist with
migrating to the latest version.


Usage
^^^^^

See lints and suggested changes for a set of source files:

.. code-block:: console

    $ fixit lint <path>

Apply suggested changes on those same files automatically:

.. code-block:: console

    $ fixit fix <path>

If given directories, Fixit will automatically recurse them, finding any files
with the ``.py`` extension, while obeying your repo's global ``.gitignore``.

See the :ref:`Command Reference <commands>` for more details.

Example
^^^^^^^

Given the following code:

.. code:: python

    # custom_object.py

    class Foo(object):
        def bar(self, value: str) -> str:
            return "value is {}".format(value)

When running Fixit, we see two separate lint errors:

.. code:: console

    $ fixit lint custom_object.py
    custom_object.py@4:15 UseFstring: Do not use printf style formatting or .format(). Use f-string instead to be more readable and efficient. See https://www.python.org/dev/peps/pep-0498/
    custom_object.py@2:0 NoInheritFromObject: Inheriting from object is a no-op.  'class Foo:' is just fine =)

We can also see any suggested changes by passing ``--diff``:

.. code:: console

    $ fixit lint --diff custom_object.py
    custom_object.py@7:0 NoInheritFromObject: Inheriting from object is a no-op.  'class Foo:' is just fine =) (has autofix)
    --- a/custom_object.py
    +++ b/custom_object.py
    @@ -6,3 +6,3 @@
    # Triggers built-in lint rules
    -class Foo(object):
    +class Foo:
        def bar(self, value: str) -> str:
    custom_object.py@9:15 UseFstring: Do not use printf style formatting or .format(). Use f-string instead to be more readable and efficient. See https://www.python.org/dev/peps/pep-0498/
    🛠️  1 file checked, 1 file with errors, 1 auto-fix available 🛠️


.. _suppressions:

Silencing Errors
^^^^^^^^^^^^^^^^

For lint rules without autofixes, it may still be useful to silence individual
errors. A simple ``# lint-ignore`` or ``# lint-fixme`` comment, either as
a trailing inline comment, or as a dedicated comment line above the code that
triggered the lint rule:

.. code:: python

    class Foo(object):  # lint-fixme: NoInheritFromObject
        ...

    # lint-ignore: NoInheritFromObject
    class Bar(object):
        ...

By providing one or more lint rule, separated by commas, Fixit can still report
issues triggered by other lint rules that haven't been listed in the comment,
but this is not required.

If no rule name is listed, Fixit will silence all rules when reported on code
associated with that comment:

.. code-block:: python

    class Foo(object):  # lint-ignore
        ...


"ignore" vs "fixme"
%%%%%%%%%%%%%%%%%%%

Both comment directives achieve the same result — silencing errors for
a particular statement of code. The semantics of using either term is left to
the user, though they are intended to be used with the following meanings:

- ``# lint-fixme`` for errors that need to be corrected or reviewed at a later
  date, but where the lint rule should be silenced temporarily for the sake
  of CI or similar external circumstances.

- ``# lint-ignore`` for errors that are false-positives (please report issues
  if this occurs with built-in lint rules) or the code is otherwise
  intentionally written or structured in a way that the lint error cannot
  be avoided.

Future versions of Fixit may offer reporting or similar tools that treat
"fixme" directives differently from "ignore" directives.


Custom Rules
^^^^^^^^^^^^

Fixit makes it easy to write and enable new lint rules, directly in your
existing codebase alongside the code they will be linting.

Lint rules in Fixit are built on top of `LibCST <https://libcst.rtfd.io>`_ 
using a :class:`~fixit.LintRule` to combine visitors and tests together
in a single unit. A (very) simple rule looks like this:

.. code:: python

    # teambread/rules/hollywood.py

    from fixit import LintRule, InvalidTestCase, ValidTestCase
    import libcst

    class HollywoodNameRule(LintRule):
        # clean code samples
        VALID = [
            ValidTestCase('name = "Susan"'),
        ]
        # code that triggers this rule
        INVALID = [
            InvalidTestCase('name = "Paul"'),
        ]

        def visit_SimpleString(self, node: libcst.SimpleString) -> None:
            if node.value in ('"Paul"', "'Paul'"):
                self.report(node, "It's underproved!")

Rules can suggest auto-fixes for the user by including a replacement CST node
when reporting an error:

.. code:: python

    def visit_SimpleString(self, node: libcst.SimpleString) -> None:
        if node.value in ('"Paul"', "'Paul'"):
            new_node = libcst.SimpleString('"Mary"')
            self.report(node, "It's underproved!", replacement=new_node)

The best lint rules will provide a clear error message, a suggested replacement,
and multiple valid and invalid tests cases that exercise as many edge cases
for the lint rule as possible.

Once written, the new lint rule can be enabled by adding it to the list
of enabled lint rules in the project's :ref:`configuration` file:

.. code:: toml

    # teambread/pyproject.toml

    [tool.fixit]
    enable = [
        ".rules.hollywood",  # enable just the rules in hollywood.py
        ".rules",  # enable rules from all files in the rules/ directory
    ]

.. note::

    The leading ``.`` (period) is required when using in-repo, or "local", lint
    rules, with a module path relative to the directory containing the config
    file. This allows Fixit to locate and import the lint rule without needing
    to install a plugin in the user's environment.

    However, be aware that if your custom lint rule needs to import other
    libraries from the repo, those libraries must be imported using *relative*
    imports, and must be contained within the same directory tree as the
    configuration file.

Once enabled, Fixit can run that new lint rule against the codebase:

.. code:: python

    # teambread/sourdough/baker.py

    def main():
        name = "Paul"
        print(f"hello {name}")

.. code:: console

    $ fixit lint --diff sourdough/baker.py
    sourdough/baker.py@7:11 HollywoodName: It's underproved! (has autofix)
    --- a/baker.py
    +++ b/baker.py
    @@ -6,3 +6,3 @@
    def main():
    -    name = "Paul"
    +    name = "Mary"
        print(f"hello {name}")
    🛠️  1 file checked, 1 file with errors, 1 auto-fix available 🛠️
    [1]

Note that the ``lint`` command only shows lint errors (and suggested changes).
The ``fix`` command will apply these suggested changes to the codebase:

.. code:: console

    $ fixit fix --automatic sourdough/baker.py
    sourdough/baker.py@7:11 HollywoodName: It's underproved! (has autofix)
    🛠️  1 file checked, 1 file with errors, 1 auto-fix available, 1 fix applied 🛠️

By default, the ``fix`` command will interactively prompt the user for each
suggested change available, which the user can then accept or decline.

Now that the suggested changes have been applied, the codebase is clean:

.. code:: console

    $ fixit lint sourdough/baker.py
    🧼 1 file clean 🧼
