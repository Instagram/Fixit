# Contributing to Fixit

## Setup

To work on Fixit, you'll need to use [Hatch](https://hatch.pypa.io/latest/).
We recommend installing it via [pipx][], but any of
[these alternatives will work](https://hatch.pypa.io/latest/install/).

Fixit requires at least Python 3.8. If you do not have an appropriate version,
or if you would like to test with newer runtimes, you can use
[pyenv](https://github.com/pyenv/pyenv) to build and manage versions.

## Developing

Fixit can be built and run locally using a clean virtualenv:

```shell-session
$ hatch shell

$ hatch env run -- fixit [args]
```

To run the test suite, type checker, and linters individually:

```shell-session
$ hatch run test

$ hatch run typecheck

$ hatch run lint:check
```

To run the full test, typecheck, and lint suite at once, you can use make:

```shell-session
$ make test lint html
```

Documentation is built using sphinx. You can generate and view the documentation
locally in your browser:

```shell-session
$ hatch run docs:build

$ open html/index.html
```


## Code style

You can ensure your changes are well formatted, and imports are sorted:

```shell-session
$ hatch run lint:fix
```

If you are using VS Code as your editor, you can use the
[µfmt plugin for VSCode](https://marketplace.visualstudio.com/items?itemName=omnilib.ufmt)
to easily enable formatting and import sorting while developing.


## VS Code

To help VS Code find your hatch environments, and all of Fixit's dependencies,
you can symlink the appropriate hatch environments into your local checkout:

```shell-session
$ hatch env create
...

$ ln -s $(hatch env find) .venv
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

[ghstack](https://github.com/ezyang/ghstack) is a tool for simplifying and
automating the process of submitting stacked PRs, where each PR in the stack
builds and depends on changes from the previous PR.

Unfortunately, ghstack requires push access to the upstream repo, so this can
only be used by project maintainers.

ghstack is a Python package, and we recommend installing it using [pipx][]:

```shell-session
$ pipx install ghstack
```

Once installed, you can run ghstack to submit a stack of PRs from your active
branch, one PR for each commit in the branch:

```shell-session
$ ghstack
```

Note that any PRs created with ghstack *cannot* be merged using the normal
Github merge UI — you must use ghstack to "land" the stack so that it can
automatically rebase and merge each commit in the correct order, and update
any outstanding PRs accordingly. You can do this by passing the URL to the
last PR in the stack that you want to land:

```shell-session
$ ghstack land $PR_URL
```

[pipx]: https://pypa.github.io/pipx/
