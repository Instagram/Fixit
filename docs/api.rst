API Reference
=============

.. module:: fixit


Lint Rules
----------

.. autoclass:: LintRule
.. autoclass:: ValidTestCase
.. autoclass:: InvalidTestCase


Frontends
---------

Simple API
^^^^^^^^^^

.. autofunction:: fixit_paths
.. autofunction:: fixit_file
.. autofunction:: print_result

.. autoclass:: LintViolation
.. autoclass:: Result


Advanced API
^^^^^^^^^^^^

.. autoclass:: fixit.ftypes.FileContent

.. autofunction:: fixit_bytes
.. autoclass:: fixit.util.capture

.. autoclass:: Config
.. autoclass:: QualifiedRule
