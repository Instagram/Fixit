# Contributing to Fixit

## Setup

Fixit requires Python 3.9 or newer. We recommend using [uv][] to install Python:

```shell-session
$ uv python install 3.13

$ uv python pin 3.13
```

You can then use `make` to create a new environment and install dependencies:

```shell-session
$ make venv
```

Once created, activate the environment:

```shell-session
$ source .venv/bin/activate

(fixit) $
```

## Developing

Once activated, Fixit can be run locally:

```shell-session
(fixit) $ fixit [args]
```

To run the test suite, type checker, and linters:

```shell-session
$ make test

$ make lint
```

To format code, sort imports, and apply automatic lint fixes:

```shell-session
$ make format
```

Documentation is built using sphinx. You can generate and view the documentation
locally in your browser:

```shell-session
$ make html

$ open html/index.html
```

To run the full test, typecheck, lint suite, and build the docs all at once:

```shell-session
$ make
```


## Submitting PRs

Before submitting PRs, please address the following items:

- Add tests exercising any fixed bugs or new functionality
- Document any changes to configuration or behavior
- Apply formatting, regenerate documentation, and run the test suite (see above)
- Summarize the high level features or behavior changes in your commit message

For most developers, we recommend using the [github cli][gh] to submit pull
requests:

```shell-session
$ gh pr create
```

If you are a Fixit maintainer, we recommend using [ghstack][] (see below):

```shell-session
$ ghstack submit
```

## Code style

You can ensure your changes are well formatted, and imports are sorted:

```shell-session
$ make format
```

If you are using VS Code as your editor, you can use the
[µfmt plugin for VSCode](https://marketplace.visualstudio.com/items?itemName=omnilib.ufmt)
to easily enable formatting and import sorting while developing.


## VS Code

Make sure you've created an environment for Fixit:

```shell-session
$ make venv
```

Now, the VS Code Python module should be able to find and offer the local
`.venv` path as an option for your active Python environment, and should then
be aware of what libraries are available, and enable "Go To Definition" for
those packages.


## git-branchless

[git-branchless](https://github.com/arxanas/git-branchless) is a useful tool
for improving your local git CLI workflow, especially within a stack of commits.
It provides a "smartlog" command (`git sl`) to help visual the hierarchy of
commits and branches in your checkout, as well as `next`/`prev` commands to
make moving through your stacks even easier:

```shell-session
amethyst@luxray ~/workspace/Fixit docs  » git sl
⋮
◇ a80603c 226d (0.x) Update 'master' (branch) references to 'main' (#220)
⋮
◆ c3f8ff9 52d (main, ᐅ docs) Include scripts dir in linters
┃
◯ 33863f4 52d (local-rules) Simple example of local rule for copyright headers
```

git-branchless is a Rust package, and can be installed with cargo:

```shell-session
$ cargo install --locked git-branchless
```

Once installed to your system, it must be enabled on each git repo that you
want to use it with, so that it can install hooks and new commands:

```shell-session
$ git branchless init
```


## ghstack

[ghstack][] is a tool for simplifying and
automating the process of submitting stacked PRs, where each PR in the stack
builds and depends on changes from the previous PR.

Unfortunately, ghstack requires push access to the upstream repo, so this can
only be used by project maintainers.

ghstack is a Python package, and we recommend installing it using [uv][]:

```shell-session
$ uv tool install ghstack
```

Once installed, you can run ghstack to submit a stack of PRs from your active
branch, one PR for each commit in the branch:

```shell-session
$ ghstack submit
```

Note that any PRs created with ghstack *cannot* be merged using the normal
Github merge UI — you must use ghstack to "land" the stack so that it can
automatically rebase and merge each commit in the correct order, and update
any outstanding PRs accordingly. You can do this by passing the URL to the
last PR in the stack that you want to land:

```shell-session
$ ghstack land $PR_URL
```

[gh]: https://cli.github.com/
[ghstack]: https://github.com/ezyang/ghstack
[pipx]: https://pypa.github.io/pipx/
[uv]: https://docs.astral.sh/uv/
