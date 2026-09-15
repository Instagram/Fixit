.. _integrations:

Integrations
------------

.. _ide_integrations:

IDE
^^^

Fixit can be used to lint as you type, to format files, and to apply or silence
individual lint errors from your editor's code action menu.

To get this functionality, install the ``lsp`` extras (e.g.
``pip install "fixit[lsp]"``) then set up an LSP client to launch and connect to
the Fixit LSP server. See the :ref:`lsp command <lsp_command>` for command
usage details.

.. _code_actions:

Code actions
%%%%%%%%%%%%

Placing the cursor on a lint error and opening your editor's code action menu
(the "light bulb" in VSCode, ``vim.lsp.buf.code_action()`` in Neovim) offers
a quickfix for every Fixit error under the cursor or selection:

- **Fix <RuleName>** applies that rule's autofix, and only that one, leaving
  every other error in the file alone. Offered only for errors that have an
  autofix.

- **Silence <RuleName> with # lint-fixme** and **Silence <RuleName> with
  # lint-ignore** insert a :ref:`suppression comment <suppressions>` above the
  statement that triggered the error, indented to match it.

To apply every available autofix in a file at once, format the document
(``textDocument/formatting``) instead.

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
For better integration with Visual Studio Code setting ``output-format`` can be set to ``vscode``.
That way VSCode opens the editor at the right position when clicking on code locations in Fixit's terminal output.
