API Reference
=============

.. module:: fixit


Lint Rules
----------

.. autoclass:: CSTLintRule
    :inherited-members: BatchableCSTVisitor
.. autoclass:: ValidTestCase
.. autoclass:: InvalidTestCase


Frontends
---------

Simple API
^^^^^^^^^^

.. autofunction:: fixit_paths
.. autofunction:: fixit_file
.. autofunction:: print_result

.. autoclass:: CodePosition
.. autoclass:: CodeRange
.. autoclass:: LintViolation
.. autoclass:: Result


Advanced API
^^^^^^^^^^^^

.. autofunction:: fixit_bytes

.. autoclass:: Config
