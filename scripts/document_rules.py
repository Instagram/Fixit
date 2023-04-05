# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path
from textwrap import dedent, fill as wrap, indent
from typing import Type

from fixit import CSTLintRule
from fixit.config import find_rules
from fixit.ftypes import QualifiedRule

from jinja2 import Template

RULES_DOC = Path(__file__).parent.parent / "docs" / "guide" / "builtins.rst"

PAGE_TPL = Template(
    r"""
..
   THIS FILE IS GENERATED — DO NOT EDIT BY HAND!
   Run `make html` or `scripts/document_rules.py` to regenerate this file.

.. module:: fixit.rules

Built-in Rules
--------------

These rules are all part of the :mod:`fixit.rules` package, and are enabled by default
unless explicitly listed in the :attr:`disable` configuration option.

{% for rule in rules %}
- :class:`{{rule.__name__}}`
{% endfor %}

{% for rule in rules %}
.. class:: {{ rule.__name__ }}
{{ rule.__doc__ }}

{% endfor %}
    """,
    trim_blocks=True,
    lstrip_blocks=True,
)


def main() -> None:
    search = QualifiedRule("fixit.rules")
    rules = list(find_rules(search))

    RULES_DOC.write_text(
        PAGE_TPL.render(
            dedent=dedent,
            indent=indent,
            hasattr=hasattr,
            len=len,
            repr=repr,
            rules=rules,
            wrap=wrap,
        )
    )


if __name__ == "__main__":
    main()
