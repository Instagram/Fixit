API Reference
=============

.. module:: fixit


Lint Rules
----------

.. autoclass:: LintRule
.. autoclass:: Valid
.. autoclass:: Invalid


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

.. autoclass:: fixit.FileContent

.. autofunction:: fixit_bytes
.. autoclass:: fixit.util.capture

.. autoclass:: Config
.. autoclass:: Options
.. autoclass:: QualifiedRule
.. autoclass:: Tags


Formatters
----------

.. autoclass:: Formatter