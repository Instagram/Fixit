.. _commands:

Commands
--------

``lint``
^^^^^^^^

Lint one or more paths, and print a list of lint errors.

.. code:: console

    $ fixit lint [--diff] [PATH ...]

.. attribute:: --diff / -d

    Show suggested fixes, in unified diff format, when available.


``fix``
^^^^^^^

Lint one or more paths, and apply suggested fixes.

.. code:: console

    $ fixit fix [--interactive | --automatic [--diff]] [PATH ...]

.. attribute:: --interactive / -i
    
    Interactively prompt the user to apply or decline suggested fixes for
    each auto-fix available. *default*

.. attribute:: --automatic / -a

    Automatically apply suggested fixes for all lint errors when available.

.. attribute:: --diff / -d

    Show applied fixes in unified diff format when applied automatically.


``debug``
^^^^^^^^^

Debug options for validating Fixit configuration.

.. code:: console

    $ fixit debug [PATH ...]


