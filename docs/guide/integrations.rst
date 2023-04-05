Integrations
------------

pre-commit
^^^^^^^^^^

Fixit can be included as a hook for `pre-commit <https://pre-commit.com>`_.

Once you `install it <https://pre-commit.com/#installation>`_, you can add
Fixit's pre-commit hook to the ``.pre-commit-config.yaml`` file in
your repository.

- To run lint rules on commit, add:

.. code:: yaml

    repos:
      - repo: https://github.com/Instagram/Fixit
        rev: 0.0.0  # replace with the Fixit version to use
        hooks:
          - id: fixit-lint

- To run lint rules and apply autofixes, add:

.. code:: yaml

    repos:
      - repo: https://github.com/Instagram/Fixit
        rev: 0.0.0  # replace with the Fixit version to use
        hooks:
          - id: fixit-fix

To read more about how you can customize your pre-commit configuration,
see the `pre-commit docs <https://pre-commit.com/#pre-commit-configyaml---hooks>`__.
