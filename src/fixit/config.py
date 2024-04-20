# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import importlib
import inspect
import logging
import pkgutil
import platform
import sys
from contextlib import contextmanager, ExitStack
from functools import reduce
from pathlib import Path
from types import ModuleType
from typing import (
    Any,
    Collection,
    Dict,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from .format import FORMAT_STYLES
from .ftypes import (
    Config,
    CwdConfig,
    is_collection,
    is_sequence,
    Options,
    OutputFormatType,
    OutputFormatTypeInput,
    QualifiedRule,
    QualifiedRuleRegex,
    RawConfig,
    RuleOptionsTable,
    RuleOptionTypes,
    T,
)
from .rule import LintRule
from .util import append_sys_path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

FIXIT_CONFIG_FILENAMES = ("fixit.toml", ".fixit.toml", "pyproject.toml")
FIXIT_LOCAL_MODULE = "fixit.local"
CWD_CONFIG_KEYS = ("output-format", "output-template")


output_formats_templates: dict[OutputFormatType, str] = {
    "fixit": "{path}@{start_line}:{start_col} {rule_name}: {message}",
    "vscode": "{path}:{start_line}:{start_col} {rule_name}: {message}",
}


log = logging.getLogger(__name__)


class ConfigError(ValueError):
    def __init__(self, msg: str, config: Optional[RawConfig] = None):
        super().__init__(msg)
        self.config = config


class CollectionError(RuntimeError):
    def __init__(self, msg: str, rule: QualifiedRule):
        super().__init__(msg)
        self.rule = rule

    def __reduce__(self) -> Tuple[Type[RuntimeError], Any]:
        return type(self), (*self.args, self.rule)


def is_rule(obj: Type[T]) -> bool:
    """
    Returns True if class is a concrete subclass of LintRule
    """
    return inspect.isclass(obj) and issubclass(obj, LintRule) and obj is not LintRule


@contextmanager
def local_rule_loader(rule: QualifiedRule) -> Iterator[None]:
    """
    Allows importing local rules from arbitrary paths as submodules of fixit.local

    Imports ``fixit.local``, a "reserved" package within the fixit namespace, and
    overrides the module's path and import spec to come from the root of the specified
    local rule. Relative imports within the local namespace should work correctly,
    though may cause collisions if parent-relative imports (``..foo``) are used.

    When the context exits, this removes all members of the ``fixit.local`` namespace
    from the global ``sys.modules`` dictionary, allowing subsequent imports of further
    local rules.

    This allows importlib to find local names within the fake ``fixit.local`` namespace,
    even if they come from arbitrary places on disk, or would otherwise have namespace
    conflicts if loaded normally using a munged ``sys.path``.
    """
    try:
        import fixit.local

        assert hasattr(fixit.local, "__path__")
        assert fixit.local.__spec__ is not None
        assert rule.root is not None

        orig_spec = fixit.local.__spec__
        fixit.local.__path__ = [rule.root.as_posix()]
        fixit.local.__spec__ = importlib.machinery.ModuleSpec(
            name=FIXIT_LOCAL_MODULE,
            loader=orig_spec.loader,
            origin=(rule.root / "__init__.py").as_posix(),
            is_package=True,
        )

        yield

    finally:
        for key in list(sys.modules):
            if key.startswith("fixit.local"):
                sys.modules.pop(key, None)


def find_rules(rule: QualifiedRule) -> Iterable[Type[LintRule]]:
    """
    Import the rule's qualified module name and return a list of collected rule classes.

    Imports the module by qualified name (eg ``foo.bar`` or ``.local.rules``), and
    then walks that module to find all lint rules.

    If a specific rule name is given, returns only the lint rule matching that name;
    otherwise returns the entire list of found rules.
    """
    try:
        if rule.local:
            with local_rule_loader(rule):
                module = importlib.import_module(rule.module, "fixit.local")
                module_rules = walk_module(module)
        else:
            module = importlib.import_module(rule.module)
            module_rules = walk_module(module)

        if rule.name:
            if value := module_rules.get(rule.name, None):
                if issubclass(value, LintRule):
                    yield value
                elif is_collection(value):
                    for v in value:
                        if issubclass(v, LintRule):
                            yield v
                else:
                    log.warning("don't know what to do with {value!r}")
            elif rule.local:
                raise CollectionError(
                    f"could not find rule {rule} in {rule.root}", rule
                )
            else:
                raise CollectionError(f"could not find rule {rule}", rule)

        else:
            for name in sorted(module_rules.keys()):
                yield module_rules[name]

    except ImportError as e:
        if rule.local:
            raise CollectionError(
                f"could not import rule(s) {rule} from {rule.root}", rule
            ) from e
        else:
            raise CollectionError(f"could not import rule(s) {rule}", rule) from e


def walk_module(module: ModuleType) -> Dict[str, Type[LintRule]]:
    """
    Given a module object, return a mapping of all rule names to classes.

    Looks at all objects of the module, and collects lint rules that match the
    :func:`is_rule` predicate.

    If the original module is a package (eg, ``foo.__init__``), also loads all
    modules from that package (ignoring sub-packages), and includes their rules in
    the final results.
    """
    rules: Dict[str, Type[LintRule]] = {}

    members = inspect.getmembers(module, is_rule)
    rules.update(members)

    if hasattr(module, "__path__"):
        for _, module_name, is_pkg in pkgutil.iter_modules(module.__path__):
            if not is_pkg:  # do not recurse to sub-packages
                mod = importlib.import_module(f".{module_name}", module.__name__)
                rules.update(walk_module(mod))

    return rules


def collect_rules(
    config: Config,
    *,
    # out-param to capture reasons when disabling rules for debugging
    debug_reasons: Optional[Dict[Type[LintRule], str]] = None,
) -> Collection[LintRule]:
    """
    Import and return rules specified by `enables` and `disables`.
    """

    all_rules: Set[Type[LintRule]] = set()
    named_enables: Set[Type[LintRule]] = set()
    if debug_reasons is not None:
        disabled_rules = debug_reasons
    else:
        disabled_rules = {}

    with ExitStack() as stack:
        if config.enable_root_import:
            path = (
                config.root / config.enable_root_import
                if isinstance(config.enable_root_import, Path)
                else config.root
            )
            stack.enter_context(append_sys_path(path))

        for qualified_rule in config.enable:
            rules = set(find_rules(qualified_rule))
            if qualified_rule.name:
                named_enables |= rules
            all_rules |= rules

        for qualified_rule in config.disable:
            disabled_rules.update(
                {
                    r: "disabled"
                    for r in find_rules(qualified_rule)
                    if r not in named_enables
                }
            )
            all_rules -= set(disabled_rules)

        if config.tags:
            disabled_rules.update(
                {R: "tags" for R in all_rules if R.TAGS not in config.tags}  # type: ignore[comparison-overlap]
            )
            all_rules -= set(disabled_rules)

        if config.python_version is not None:
            disabled_rules.update(
                {
                    R: "python-version"
                    for R in all_rules
                    if config.python_version not in SpecifierSet(R.PYTHON_VERSION)
                }
            )
            all_rules -= set(disabled_rules)

        materialized_rules = [R() for R in all_rules]

    return materialized_rules


def locate_configs(path: Path, root: Optional[Path] = None) -> List[Path]:
    """
    Given a file path, locate all relevant config files in priority order.

    Walking upward from target path, creates a list of candidate paths that exist
    on disk, ordered from nearest/highest priority to further/lowest priority.

    If root is given, only return configs between path and root (inclusive), ignoring
    any paths outside of root, even if they would contain relevant configs.
    If given, root must contain path.

    Returns a list of config paths in priority order, from highest priority to lowest.
    """
    results: List[Path] = []

    if not path.is_dir():
        path = path.parent

    root = root.resolve() if root is not None else Path(path.anchor)
    path.relative_to(root)  # enforce path being inside root

    while True:
        candidates = (path / filename for filename in FIXIT_CONFIG_FILENAMES)
        for candidate in candidates:
            if candidate.is_file():
                results.append(candidate)

        if path == root or path == path.parent:
            break

        path = path.parent

    return results


def read_configs(paths: List[Path]) -> List[RawConfig]:
    """
    Read config data for each path given, and return their raw toml config values.

    Skips any path with no — or empty — `tool.fixit` section.
    Stops early at any config with `root = true`.

    Maintains the same order as given in paths, minus any skipped files.
    """
    configs: List[RawConfig] = []

    for path in paths:
        path = path.resolve()
        content = path.read_text()
        data = tomllib.loads(content)
        fixit_data = data.get("tool", {}).get("fixit", {})

        if fixit_data:
            config = RawConfig(path=path, data=fixit_data)
            configs.append(config)

            if config.data.get("root", False):
                break

    return configs


def get_sequence(
    config: RawConfig, key: str, *, data: Optional[Dict[str, Any]] = None
) -> Sequence[str]:
    value: Sequence[str]
    if data:
        value = data.pop(key, ())
    else:
        value = config.data.pop(key, ())

    if not is_sequence(value):
        raise ConfigError(
            f"{key!r} must be array of values, got {type(key)}", config=config
        )

    return value


def get_options(
    config: RawConfig, key: str, *, data: Optional[Dict[str, Any]] = None
) -> RuleOptionsTable:
    if data:
        mapping = data.pop(key, {})
    else:
        mapping = config.data.pop(key, {})

    if not isinstance(mapping, Mapping):
        raise ConfigError(
            f"{key!r} must be mapping of values, got {type(key)}", config=config
        )

    rule_configs: RuleOptionsTable = {}
    for rule_name, rule_config in mapping.items():
        rule_configs[rule_name] = {}
        for key, value in rule_config.items():
            if not isinstance(value, RuleOptionTypes):
                raise ConfigError(
                    f"{key!r} must be one of {RuleOptionTypes}, got {type(value)}",
                    config=config,
                )

            rule_configs[rule_name][key] = value

    return rule_configs


def parse_rule(
    rule: str, root: Path, config: Optional[RawConfig] = None
) -> QualifiedRule:
    """
    Given a raw rule string, parse and return a QualifiedRule object
    """
    if not (match := QualifiedRuleRegex.match(rule)):
        raise ConfigError(f"invalid rule name {rule!r}", config=config)

    group = match.groupdict()
    module = group["module"]
    name = group["name"]
    local = group["local"]

    if local:
        return QualifiedRule(module, name, local, root)
    else:
        return QualifiedRule(module, name)


def merge_configs(
    path: Path, raw_configs: List[RawConfig], root: Optional[Path] = None
) -> Config:
    """
    Given multiple raw configs, merge them in priority order.

    Assumes raw_configs are given in order from highest to lowest priority.
    """

    config: RawConfig
    enable_root_import: Union[bool, Path] = Config.enable_root_import
    enable_rules: Set[QualifiedRule] = {QualifiedRule("fixit.rules")}
    disable_rules: Set[QualifiedRule] = set()
    rule_options: RuleOptionsTable = {}
    target_python_version: Optional[Version] = Version(platform.python_version())
    target_formatter: Optional[str] = None

    def process_subpath(
        subpath: Path,
        *,
        enable: Sequence[str] = (),
        disable: Sequence[str] = (),
        options: Optional[RuleOptionsTable] = None,
        python_version: Any = None,
        formatter: Optional[str] = None,
    ) -> None:
        nonlocal target_python_version
        nonlocal target_formatter

        subpath = subpath.resolve()
        try:
            path.relative_to(subpath)
        except ValueError:  # not relative to subpath
            return

        config_dir = config.path.parent
        for rule in enable:
            qual_rule = parse_rule(rule, config_dir, config)
            enable_rules.add(qual_rule)
            disable_rules.discard(qual_rule)

        for rule in disable:
            qual_rule = parse_rule(rule, config_dir, config)
            enable_rules.discard(qual_rule)
            disable_rules.add(qual_rule)

        if options:
            rule_options.update(options)

        if python_version is not None:
            if python_version:
                try:
                    target_python_version = Version(python_version)
                except InvalidVersion:
                    raise ConfigError(
                        f"'python-version' {python_version!r} is not valid",
                        config=config,
                    )

            else:  # disable versioning, aka python-version = ""
                target_python_version = None

        if formatter:
            if formatter not in FORMAT_STYLES:
                raise ConfigError(
                    f"'formatter' {formatter!r} not supported", config=config
                )

            target_formatter = formatter

    for config in reversed(raw_configs):
        if root is None:
            root = config.path.parent

        data = config.data
        if data.pop("root", False):
            root = config.path.parent

        if value := data.pop("enable-root-import", False):
            if root != config.path.parent:
                raise ConfigError(
                    "enable-root-import not allowed in non-root configs", config=config
                )
            if isinstance(value, str):
                value_path = Path(value)
                if value_path.is_absolute():
                    raise ConfigError(
                        "enable-root-import: absolute paths not allowed", config=config
                    )
                if ".." in value_path.parts:
                    raise ConfigError(
                        "enable-root-import: '..' components not allowed", config=config
                    )
                enable_root_import = value_path
            else:
                enable_root_import = True

        process_subpath(
            config.path.parent,
            enable=get_sequence(config, "enable"),
            disable=get_sequence(config, "disable"),
            options=get_options(config, "options"),
            python_version=config.data.pop("python-version", None),
            formatter=config.data.pop("formatter", None),
        )

        for override in get_sequence(config, "overrides"):
            if not isinstance(override, dict):
                raise ConfigError("'overrides' requires array of tables", config=config)

            subpath = override.get("path", None)
            if not subpath:
                raise ConfigError(
                    "'overrides' table requires 'path' value", config=config
                )

            subpath = config.path.parent / subpath
            process_subpath(
                subpath,
                enable=get_sequence(config, "enable", data=override),
                disable=get_sequence(config, "disable", data=override),
                options=get_options(config, "options", data=override),
                python_version=override.pop("python-version", None),
                formatter=override.pop("formatter", None),
            )

        for key in data.keys():
            if key not in CWD_CONFIG_KEYS:
                log.warning("unknown configuration option %r", key)

    return Config(
        path=path,
        root=root or Path(path.anchor),
        enable_root_import=enable_root_import,
        enable=sorted(enable_rules),
        disable=sorted(disable_rules),
        options=rule_options,
        python_version=target_python_version,
        formatter=target_formatter,
    )


def generate_config(
    path: Path, root: Optional[Path] = None, *, options: Optional[Options] = None
) -> Config:
    """
    Given a file path, walk upwards looking for and applying cascading configs
    """
    path = path.resolve()

    if root is not None:
        root = root.resolve()

    if options and options.config_file:
        config_paths = [options.config_file]
    else:
        config_paths = locate_configs(path, root=root)

    raw_configs = read_configs(config_paths)
    config = merge_configs(path, raw_configs, root=root)

    if options:
        if options.tags:
            config.tags = options.tags

        if options.rules:
            config.enable = list(options.rules)
            config.disable = []

    return config


def get_cwd_config(options: Optional[Options] = None) -> CwdConfig:
    config = CwdConfig()
    if options and options.config_file:
        paths = [options.config_file]
    else:
        cwd = Path.cwd()
        paths = locate_configs(cwd, cwd)

    raw_configs = read_configs(paths)

    output_format: Optional[OutputFormatTypeInput] = None
    output_template: Optional[str] = None
    for raw_config in raw_configs:

        if output_format is None:
            output_format = raw_config.data.get("output-format")
        if output_template is None:
            output_template = raw_config.data.get("output-template")

    config.output_format = output_format or "fixit"
    config.output_template = output_template or output_formats_templates["fixit"]

    if options:
        if options.output_format:
            config.output_format = options.output_format

        if options.output_template:
            config.output_template = options.output_template

    return config
