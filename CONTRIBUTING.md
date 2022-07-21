# Contributing to Fixit

## Setup

Fixit can be built and tested locally using a clean virtualenv:

```sh
$ make venv
```

Or using [tox](https://tox.wiki):

```sh
$ pip install tox
```

## Developing

With a virtualenv (as setup above), you can run the test suite and linters:

```sh
$ make test lint
```

or do this with tox:

```sh
$ tox -p
```

## Code style

You can ensure your changes are well formatted, and imports are sorted

```sh
$ make format
```

or directly with [µfmt](https://ufmt.omnilib.dev):

```sh
$ ufmt format fixit
```
