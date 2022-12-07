# Contributing to Fixit

## Setup

To work on Fixit, you'll need to use [Hatch](https://hatch.pypa.io/latest/).
We recommend installing it via `pipx install hatch`, but any of
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
