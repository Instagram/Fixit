# Fixit


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

    pyre check

To generate documents, do the following in the root:

.. code-block:: shell

    tox -e docs


License
=======

Fixit is MIT licensed, as found in the LICENSE file.
