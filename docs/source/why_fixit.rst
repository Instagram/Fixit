==========
Why Fixit?
==========

**There are many Python linter tools. Why do we need another?**

Linters are built to help developers write better code and many good linters have been built.
In a large codebase, tons of lint suggestions can slow developers down.
Developers may spend too much time on fixing code quality suggestions and cannot focus more
on important progress.
At some point, they may start to ignore lint suggestions, even the important ones.

We'd like to help developers move faster by **auto-fixing** lint violations.
The first challenge is most tools analyze source code using
`AST <https://docs.python.org/3/library/ast.html>`_ which doesn't preserve formatting info
(comments, whitespaces, etc) and makes it hard to build autofix.
We built `LibCST <https://github.com/Instagram/LibCST>`_ to make parsing and modifying
source code as a Concrete Syntax Tree easily.

Learning from building Flake8 plugin
====================================

Many of our old lint rules are implemented in a monolithic single-file
`Flake8 plugin <https://flake8.pycqa.org/en/latest/plugin-development/index.html>`_.
This offered a lot of flexibility and helped facilitate a shared structure for the rules,
but it led to a number of severe downsides:

- Rules were highly coupled, with a significant amount of shared state and helper functions.
  It was common to make a small change to one lint rule, and break other lint rules.
  Because of poor testing practices, these breakages could be missed.
- It wasn't possible to run rules in isolation, making benchmarking and testing more difficult.
  Disabling a rule in Flake8 consists of running the whole linter and
  filtering out the disabled results.
- Visitors were responsible for visiting their children.
  Forgetting to do this could break lint coverage inside of the given construct.
- To work around some of these issues, developers would often define their own node visitor.
  Traversing the AST multiple times slows down the linter.

The result was a large file with lots of visitors and helper functions which was hard to
develop upon.

Design Principles
=================
When designing Fixit, we used the following list of principles.

- **Autofix.** Lint rules should provide autofix whenever possible to help developer write
  better code faster. The autofix can run as a codemod on an existing codebase to avoid
  introducing tons of lint violations when adding a new lint rule.
- **Modular.** A lint rule is a standalone class which keeps its own logic and states from
  other rules. That keeps developing a lint rule simple and doesn't break other rules.
- **Fast.** All lint rule run on a single syntax tree traversal and reuse shared metadata
  to provide lint suggestions fast.
- **Configurable.** Each lint rule is configurable in the config file. That makes lint rules
  highly customizable. When disable a lint rule, the rule doesn't run at all.
- **Ease of Test.** Test a lint rule is as simple as providing code examples. The examples
  are also used in document to help developers understand the line rule easily.