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


Usage
^^^^^

See lints and suggested changes for a set of source files:

.. code-block:: console

    $ fixit lint <paths>

Apply suggested changes on those same files automatically:

.. code-block:: console

    $ fixit fix <paths>

If given directories, Fixit will automatically recurse them, finding any files
with the ``.py`` extension, while obeying your repo's global ``.gitignore``.


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
    custom_object.py@4:15 UseFstringRule: Do not use printf style formatting or .format(). Use f-string instead to be more readable and efficient. See https://www.python.org/dev/peps/pep-0498/
    custom_object.py@2:0 NoInheritFromObjectRule: Inheriting from object is a no-op.  'class Foo:' is just fine =)


Custom Rules
^^^^^^^^^^^^

Fixit makes it easy to write and enable new lint rules, directly in your
existing codebase alongside the code they will be linting.

Lint rules in Fixit are built on top of `LibCST <https://libcst.rtfd.io>`_ 
using a :class:`~fixit.CSTLintRule` to combine visitors and tests together
in a single unit. A (very) simple rule looks like this:

.. code:: python

    # teambread/rules/hollywood.py

    from fixit import CSTLintRule, InvalidTestCase, ValidTestCase
    import libcst

    class HollywoodNameRule(CSTLintRule):
        # clean code samples
        VALID = [
            ValidTestCase('name = "Susan"'),
        ]
        # code that triggers this rule
        INVALID = [
            InvalidTestCase('name = "Paul"'),
        ]

        def visit_SimpleString(self, node: libcst.SimpleString) -> None:
            if name.value in ('"Paul"', "'Paul'"):
                self.report(node, "It's underproved!")

Rules can suggest auto-fixes for the user by including a replacement CST node
when reporting an error:

.. code:: python

    def visit_SimpleString(self, node: libcst.SimpleString) -> None:
        if name.value in ('"Paul"', "'Paul'"):
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

    $ fixit lint teambread/sourdough/baker.py
    sourdough/baker.py@2:7 HollywoodNameRule: It's underproved!