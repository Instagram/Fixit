# Changelog

## 0.1.4 - 2021-07-30
### Updated
- Fix typo [#163](https://github.com/Instagram/Fixit/pull/163)
- Refactor ipc_main [#175](https://github.com/Instagram/Fixit/pull/175)
- Refactor search yaml [#172](https://github.com/Instagram/Fixit/pull/172)
- Bug fix for UseTypesFromTypingRule [#178](https://github.com/Instagram/Fixit/pull/178)
- Fix sentinel type error [#187](https://github.com/Instagram/Fixit/pull/187)
- Autofix docstrings [#190](https://github.com/Instagram/Fixit/pull/190)
- Fix pyre type-check errors [#196](https://github.com/Instagram/Fixit/pull/196)
- Add JSON Schema for Fixit configs [#188](https://github.com/Instagram/Fixit/pull/188)
- Adds allow_list_rules setting for configs [#184](https://github.com/Instagram/Fixit/pull/184)
- Adds allow_list_rules to schema [#197](https://github.com/Instagram/Fixit/pull/197)
- Fix run_rules bug [#200](https://github.com/Instagram/Fixit/pull/200)

## 0.1.3 - 2020-12-09

### New Rules
- Add NoRedundantArgumentsSuperRule [#154](https://github.com/Instagram/Fixit/pull/154)
- Add ExplicitFrozenDataclassRule [#158](https://github.com/Instagram/Fixit/pull/158)
- Add UseLintFixmeCommentRule [#161](https://github.com/Instagram/Fixit/pull/161)
- Add UseAssertInRule [#159](https://github.com/Instagram/Fixit/pull/159)

### Updated
- await async rule does not account for decorators [#150](https://github.com/Instagram/Fixit/pull/150)
- Allow glob patterns instead of parent dirs for matching configs [#156](https://github.com/Instagram/Fixit/pull/156)

## 0.1.2 - 2020-10-29

### New Rules
- Add SortedAttributesRule [#149](https://github.com/Instagram/Fixit/pull/149)

### Added
- New unified `fixit` CLI [#148](https://github.com/Instagram/Fixit/pull/148)

### Updated
- Add `use_noqa` configuration to control support of the `noqa` Flake8 suppression comment. Defaults to `False` [#151](https://github.com/Instagram/Fixit/pull/151)

## 0.1.1 - 2020-10-08

### New Rules
- Add UseAssertIsNotNoneRule [#144](https://github.com/Instagram/Fixit/pull/144)
- Add MissingHeaderRule to check copyright header comments [#142](https://github.com/Instagram/Fixit/pull/142)
- Add NoStringTypeAnnotationRule [#140](https://github.com/Instagram/Fixit/pull/140)
- Add NoNamedTupleRule [#136](https://github.com/Instagram/Fixit/pull/136)
- Add NoAssertTrueForComparisonsRule to catch some incorrect uses of assertTrue() [#135](https://github.com/Instagram/Fixit/pull/135)
- Add CollapseIsinstanceChecksRule [#116](https://github.com/Instagram/Fixit/pull/116)
- Add NoUnnecessaryFormatStringRule and UseFstringRule [#101](https://github.com/Instagram/Fixit/pull/101)
- Add NoRedundantLambdaRule. [#112](https://github.com/Instagram/Fixit/pull/112)

### Added
- add_new_rule CLI for adding new rule file [#123](https://github.com/Instagram/Fixit/pull/123), [#131](https://github.com/Instagram/Fixit/pull/131)

### Updated
- Ensure first lines remain intact with AddMissingHeaderRule [#143](https://github.com/Instagram/Fixit/pull/143)
- Documentation improvements: [#113](https://github.com/Instagram/Fixit/pull/113), [#117](https://github.com/Instagram/Fixit/pull/117),
[#118](https://github.com/Instagram/Fixit/pull/118), [#120](https://github.com/Instagram/Fixit/pull/120)
[#133](https://github.com/Instagram/Fixit/pull/133), [#138](https://github.com/Instagram/Fixit/pull/138)
- Improve test message [#137](https://github.com/Instagram/Fixit/pull/137)

## 0.1.0 - 2020-09-02

### Added

 - First public release of Fixit.
 - Python Lint Framework based on LibCST with autofix functionality.
 - Comes pre-packaged with a set of built-in lint rules.
 - Provides scripts for linting, autofixing and inserting lint suppressions into source code.
 - Provides development kit to build and enforce custom lint rules.
 - Full suite of unit tests.
