Quick Start
-----------


Setup
^^^^^

Install Fixit from PyPI:

.. code-block:: console

   $ pip install --pre "fixit >1"

By default, Fixit enables all of the lint rules that ship with Fixit,
all of which are part of the :mod:`fixit.rules` package.

Usage
^^^^^

See lints and suggested changes for a set of source files:

.. code-block:: console

   $ fixit lint <paths>

Apply suggested changes on those same files automatically:

.. code-block:: console

   $ fixit fix <paths>
