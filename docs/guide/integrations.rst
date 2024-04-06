.. _integrations:

Integrations
------------

.. _ide_integrations:

IDE
^^^

Fixit can be used to lint as you type as well as to format files.

To get this functionality, install the ``lsp`` extras (e.g.
``pip install "fixit[lsp]"``) then set up an LSP client to launch and connect to
the Fixit LSP server. See the :ref:`lsp command <lsp_command>` for command
usage details.

Examples of client setup:

- VSCode:

  - `Generic LSP Client <https://github.com/llllvvuu/vscode-glspc>`_
    (via GitHub; requires configuration)
  - `Fixit (Unofficial) <https://marketplace.visualstudio.com/items?itemName=llllvvuu.fixit-unofficial>`_
    (via VSCode Marketplace; compiled from Generic LSP Client with preset
    configuration for Fixit)

- Neovim: `nvim-lspconfig <https://github.com/neovim/nvim-lspconfig>`_:

.. code:: lua

      require("lspconfig.configs").fixit = {
        default_config = {
          cmd = { "fixit", "lsp" },
          filetypes = { "python" },
          root_dir = require("lspconfig").util.root_pattern(
            "pyproject.toml", "setup.py", "requirements.txt", ".git",
          ),
          single_file_support = true,
        },
      }

      lspconfig.fixit.setup({})

- `Other IDEs <https://microsoft.github.io/language-server-protocol/implementors/tools/>`_

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


VSCode
^^^^^^
For integration with Visual Studio Code setting ``output-format`` to ``{path}:{start_line}:{start_col} {rule_name}: {message}`` is recommended.
That way VSCode opens the editor at the right position when clicking on filenames in Fixit's terminal output.
