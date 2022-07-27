# Contributing to Fixit

## Setup

To work on Fixit, you'll need to use [Hatch](https://hatch.pypa.io/latest/). We recommend installing it via `pipx install hatch`, but any of [these alternatives will work](https://hatch.pypa.io/latest/install/).

Fixit can be built and tested locally using a clean virtualenv:

```sh
$ hatch shell
```

## Developing

To run tests:

```sh
$ hatch run test
```

To run linters:

```sh
$ hatch run lint:check
```

## Code style

You can ensure your changes are well formatted, and imports are sorted

```sh
$ hatch run lint:fix
```
