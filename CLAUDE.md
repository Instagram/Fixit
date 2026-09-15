# CLAUDE.md

Notes for AI coding agents working in this repository. Human contributors should
start with [CONTRIBUTING.md](CONTRIBUTING.md); this file only covers the things
that are easy to get wrong here.

## What Fixit is

A lint framework built on [LibCST](https://libcst.readthedocs.io). Rules are
CST visitors that `self.report(...)` a violation, optionally with a
`replacement` node that Fixit can apply as an autofix.

## Setup

```shell-session
$ make venv && source .venv/bin/activate
```

`make venv` uses `uv` when it is on `PATH`, and falls back to `python -m venv`.
The environment installs the `dev,docs,lsp,pretty` extras. Requires Python
3.10+.

## Checks

| Command      | What it runs                                          | Gated by CI |
| ------------ | ----------------------------------------------------- | ----------- |
| `make test`  | `python -m fixit.tests` + `pyrefly check`              | yes         |
| `make html`  | regenerates `docs/guide/builtins.rst`, builds sphinx   | yes[^1]     |
| `make lint`  | flake8, Fixit on itself, `ufmt check`, copyright check | no          |
| `make format`| `ufmt format` (black + usort)                          | —           |

[^1]: the docs job runs `git diff --exit-code` afterwards, so committed
generated docs must match what `make html` produces.

Run the full suite with bare `make`. To run one test module:

```shell-session
$ python -m unittest fixit.tests.lsp -v
```

## Layout

| Path                    | Purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `src/fixit/rule.py`     | `LintRule` base class, `report()`, ignore directives  |
| `src/fixit/engine.py`   | `LintRunner`: parse, visit, apply replacements        |
| `src/fixit/api.py`      | `fixit_bytes` and friends — the public entry points   |
| `src/fixit/config.py`   | `fixit.toml` / `pyproject.toml` discovery and merging |
| `src/fixit/ftypes.py`   | `Config`, `Options`, `LintViolation`, `Result`        |
| `src/fixit/lsp.py`      | language server (requires the `lsp` extra)            |
| `src/fixit/rules/`      | built-in rules, auto-discovered                       |
| `src/fixit/upgrade/`    | rules that migrate user code to newer Fixit APIs      |
| `src/fixit/tests/`      | the test suite                                        |

## Things that will bite you

**Generated files — do not hand-edit.**

- `docs/guide/builtins.rst` — regenerate with `make html` (or
  `python scripts/document_rules.py`) and commit the result.
- `CHANGELOG.md` — written by `attribution` at release time.
- `src/fixit/__version__.py` — written by `hatch-vcs`, and gitignored.

**New test modules must be imported in `src/fixit/tests/__init__.py`**, or
`python -m fixit.tests` will silently not run them. Tests are plain
`unittest` — there is no pytest, and no auto-discovery.

**Rule tests are generated.** `add_lint_rule_tests_to_module` turns each rule's
`VALID` / `INVALID` class attributes into test cases. Add coverage for a rule by
adding `Valid(...)` / `Invalid(...)` entries to the rule itself, not by writing a
test module.

**Every tracked source file needs the Meta copyright header** (4 lines, copy it
from any existing file). `scripts/check_copyright.py` enforces this.

**The `lsp` extra is optional for users, but not for the test suite.**
`src/fixit/lsp.py` imports `pygls`, so `cli.py` imports it lazily, inside the
`lsp` command. Nothing in `src/fixit/` outside `lsp.py` may import it at module
scope. The tests do (`tests/smoke.py`, `tests/lsp.py`), so running them needs
`make install` with the `lsp` extra — which is what CI does.

**Typing style is conservative.** The codebase targets Python 3.10 and uses
`typing.List` / `Optional[...]` rather than `list[...]` / `X | None`. Match the
surrounding file.

**`make lint` may already fail on `main`** when the pinned `black` version
drifts ahead of what the tree was last formatted with. Check whether a failure
predates your change before "fixing" unrelated files — CI does not run
`make lint`.

## Writing a rule

```python
class NoThing(LintRule):
    MESSAGE = "don't do the thing"
    VALID = [Valid("good = 1")]
    INVALID = [Invalid("bad = 1", expected_replacement="good = 1")]

    def visit_Assign(self, node: cst.Assign) -> None:
        self.report(node, replacement=node.with_changes(...))
```

Put it in `src/fixit/rules/<snake_case_name>.py` (one rule per file, matching
the class name), then run `make html` to regenerate the rule docs.

## The lint/fix protocol

`fixit_bytes` is a generator that yields a `Result` per violation and accepts a
`bool` sent back for each one — `True` applies that violation's fix. It returns
the final file content. `fixit.util.capture` wraps it so the return value is
reachable after iterating. `autofix=True` applies everything regardless of what
is sent.

Applying one fix out of many goes through
`LintRunner.apply_replacements([violation])` followed by `format_module(...)`;
don't splice replacement source text into the reported range, because a rule may
report a position that doesn't cover the node being replaced, and the configured
formatter may reflow the result.
