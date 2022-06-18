.. image:: docs/source/_static/logo/logo.svg
   :width: 600 px
   :alt: Fixit

|readthedocs-badge| |codecov-badge| |pypi-badge| |pypi-download|

.. |readthedocs-badge| image:: https://readthedocs.org/projects/pip/badge/?version=latest&style=flat
   :target: https://fixit.readthedocs.io/en/latest/
   :alt: Documentation

.. |codecov-badge| image:: https://codecov.io/gh/Instagram/Fixit/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/Instagram/Fixit/branch/main

.. |pypi-badge| image:: https://img.shields.io/pypi/v/fixit.svg
   :target: https://pypi.org/project/fixit
   :alt: PYPI

.. |pypi-download| image:: https://pepy.tech/badge/fixit/month
   :target: https://pepy.tech/project/fixit/month
   :alt: PYPI Download

.. intro-start

:title:`A lint framework that writes better Python code for you.`

Fixit is a lint framework that complements `Flake8 <https://github.com/PyCQA/flake8>`_.
It’s based on `LibCST <https://github.com/Instagram/LibCST/>`_ which makes it possible
to provide **auto-fixes**.
Lint rules are made easy to build through pattern matching, a test toolkit,
and utility helpers (e.g. scope analysis) for non-trivial boilerplate.
It is optimized for efficiency, easy to customize and comes with many builtin lint rules.

.. intro-end

Getting Started
---------------

To install Fixit::

  pip install fixit

Fixit provides CLI commands.
To run built-in Fixit rules on existing code to get code quality suggestions::

  python -m fixit.cli.run_rules

To apply autofix on existing code::

  python -m fixit.cli.apply_fix

You can learn more about how to `configure Fixit <https://fixit.readthedocs.io/en/latest/getting_started.html#Configuration-File>`_,
`build a lint rule <https://fixit.readthedocs.io/en/latest/build_a_lint_rule.html>`_,
`test a lint rule <https://fixit.readthedocs.io/en/latest/test_a_lint_rule.html>`_ from our tutorials.
Try it out with our `notebook examples <https://fixit.readthedocs.io/en/latest/getting_started.html>`_.

Further Reading
---------------
- `Static Analysis at Scale: An Instagram Story. <https://instagram-engineering.com/static-analysis-at-scale-an-instagram-story-8f498ab71a0c>`_

Development
-----------

Start by setting up and activating a virtualenv:

.. code-block:: shell

    git clone git@github.com:Instagram/Fixit.git fixit
    cd fixit
    python3 -m venv ../fixit-env/  # just an example, put this wherever you want
    source ../fixit-env/bin/activate
    pip install --upgrade pip  # optional, if you have an old system version of pip
    pip install -r requirements.txt -r requirements-dev.txt
    # If you're done with the virtualenv, you can leave it by running:
    deactivate

We use `ufmt <https://ufmt.omnilib.dev/en/stable/>`_ to format code. To format
changes to be conformant, run the following in the root:

.. code-block:: shell

    tox -e autofix

To run all tests, you'll need to install `tox <https://tox.readthedocs.io/en/latest/>`_
and do the following in the root: (use py37, py38 to choose from Python version 3.7 or 3.8)::

    tox -e py38

You can also run individual unit tests by specifying a module like
this::

    tox -e py38 -- fixit.common.tests.test_report

To run all test cases of a specific rule (e.g. ``NoInheritFromObjectRule``)::

    tox -e py38 -- fixit.tests.NoInheritFromObjectRule

See the `unittest documentation <https://docs.python.org/3/library/unittest.html>`_
for more examples of how to run tests.

We use `Pyre <https://github.com/facebook/pyre-check>`_ for type-checking. To
verify types for the library, do the following in the root::

    pyre --preserve-pythonpath check

To generate documentation, do the following in the root:

.. code-block:: shell

    tox -e docs


License
=======

Fixit is `MIT licensed <LICENSE>`_, as found in the LICENSE file.

.. fb-docs-start

Privacy Policy and Terms of Use
===============================

- `Privacy Policy <https://opensource.facebook.com/legal/privacy>`_
- `Terms of Use <https://opensource.facebook.com/legal/terms>`_

.. fb-docs-end
