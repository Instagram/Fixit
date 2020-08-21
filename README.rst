.. image:: docs/source/_static/logo/logo.svg
   :width: 600 px
   :alt: Fixit

A lint framework writes better Python code for you.

.. intro-start

Fixit is a lint framework that compliments `Flake8 <https://github.com/PyCQA/flake8>`_.
It’s based on `LibCST <https://github.com/Instagram/LibCST/>`_ which makes it possible
to provide **auto-fixes**.
Lint rules are made easy to build through matcher pattern, test toolkit,
utility helpers (e.g. scope analysis) for non-trivial boilerplate.
It is optimized for efficiency, easy to customize and comes with many builtin lint rules.

.. intro-end

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

We use `isort <https://isort.readthedocs.io/en/stable/>`_ and `black <https://black.readthedocs.io/en/stable/>`_
to format code. To format changes to be conformant, run the following in the root:

.. code-block:: shell

    tox -e autofix

To run all tests, you'll need to install `tox <https://tox.readthedocs.io/en/latest/>`_
and do the following in the root:

.. code-block:: shell

    tox -e py37

You can also run individual tests by using unittest and specifying a module like
this:

.. code-block:: shell

    python -m unittest fixit.common.testing.LintRuleTest

See the `unittest documentation <https://docs.python.org/3/library/unittest.html>`_
for more examples of how to run tests.

We use `Pyre <https://github.com/facebook/pyre-check>`_ for type-checking. To
verify types for the library, do the following in the root:

.. code-block:: shell

    pyre --preserve-pythonpath check

To generate documents, do the following in the root:

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