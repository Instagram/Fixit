# FP1: Hierarchical configuration

Rather than using YAML, which is prone to errors and ambiguous grammar, or JSON, which
is impossible* to read and modify by a user, this proposes a new config format based on
[TOML](https://toml.io) format. This allows logically nested configuration without a
physically nested data format, and uses a better specified format with good support
in Python (as `tomli` in PyPI, or `tomllib` in stdlib with 3.11).

This specific proposal was designed with the need for overriding global or default
values on any number of subpaths, so that individual paths (or submodules), within
a multirepo or monorepo can have their own custom configuration or lint rules.

Furthermore, individual projects should be able to have their own config files (with
relative paths) that are also read and override global config, to provide predictable
and consistent linting results when linting the project separately or within the
monorepo.


## Structure

Configuration at any given path must be located either in the standardized
`pyproject.toml` file, or a separate `fixit.toml` file. To follow PEP 518, everything
in `pyproject.toml` must be under the `tool.<name>` table, which would be `tool.fixit`,
so we should use that same table name in `fixit.toml` for consistency.

Selection of rules could ideally be a simple set of enabled and disabled rules,
but it also makes sense to allow specifying groups of rules by their package/module
name, as well as their fully qualified names. This is similar to enabling an entire
group of lint rules in flake8 with `select = E,F` vs single rules with `ignore = E501`.


## Subpath overrides

Overriding global/default values should be possible both via additional tables in a
top-level config file, or by separate config files within those subpaths. Overrides
should be applied to all files within the relative subpaths, accounting for further
nested overrides.

It may be worth supporting an `inherit = False` or `root = true` type of setting,
to ignore all parent/global configs, and prevent inconsistent results when, eg,
linting an OSS project exported to Github vs within the originating monorepo.

Overrides should share key names with the global/default values whenever possible.
When inheriting parent values, subpath overrides should generally be set unions with
parent values. Further semantics/heuristics may need to be applied when a subpath
attempts to enable a rule that is otherwise disabled by global or parent configuration.


## Proposed examples

Global/default configuration:

```toml
[tool.fixit]
inherit = false  # ignore all configs above this one
enable = [
    "fixit",  # enable everything from a top-level package
    "fixit.core",  # only rules from a specific module
    "fixit.core.OneRule",  # enable a specific rule by fully qualified name
]
disable = [
    "fixit.opinions",  # disable an entire module
    "fixit.style.LineLength",  # disable a specific rule by fully qualified name
]
```

Overrides, option A, array-of-tables:

```toml
[[tool.fixit.overrides]]
path = "foo"

# add to the set of enabled/disabled rules
enable = [
    "foo.rules",  # enable a local module with multiple rules
]
disable = [
    "fixit.core.RuleFour",  # disable a core rule by fully qualified name
]

[[tools.fixit.overrides]]
path = "foo/bar/baz"

enable = ["..."]
disable = ["..."]
```

Overrides, option B, paths-within-table-names:
```toml
[tool.fixit.overrides.foo]
enable = ["..."]
disable = ["..."]

[tool.fixit.overrides."foo/bar/baz"]
enable = ["..."]
disable = ["..."]
```

