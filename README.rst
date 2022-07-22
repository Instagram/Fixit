.. image:: docs/_static/logo/logo.svg
   :width: 600 px
   :alt: Fixit

|readthedocs-badge| |pypi-badge|

.. |readthedocs-badge| image:: https://readthedocs.org/projects/pip/badge/?version=latest&style=flat
   :target: https://fixit.readthedocs.io/en/latest/
   :alt: Documentation

.. |pypi-badge| image:: https://img.shields.io/pypi/v/fixit.svg
   :target: https://pypi.org/project/fixit
   :alt: PYPI


Setup
-----

Install Fixit from PyPI:

.. code-block:: console

   $ pip install fixit


Usage
-----

See lints and suggested changes for a set of source files:

.. code-block:: console

   $ fixit lint <paths>

Apply suggested changes on those same files automatically:

.. code-block:: console

   $ fixit fix <paths>

For more details, see the `user guide <https://fixit.rtfd.io>`_.


License
-------

Fixit is `MIT licensed <LICENSE>`_, as found in the LICENSE file.
