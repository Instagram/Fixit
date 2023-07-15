# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path
from textwrap import dedent, indent

from fixit.config import find_rules
from fixit.ftypes import QualifiedRule

from jinja2 import Template

RULES = ["fixit.rules", "fixit.upgrade"]

RULES_DOC = Path(__file__).parent.parent / "docs" / "guide" / "builtins.rst"

PAGE_TPL = Template(
    r"""
..
   THIS FILE IS GENERATED - DO NOT EDIT BY HAND!
   Run `make html` or `scripts/document_rules.py` to regenerate this file.

.. _builtin-rules:

Built-in Rules
--------------

{% for pkg in packages %}
- :mod:`{{ pkg.module }}`
{% endfor %}

{% for pkg, rules in packages.items() %}

``{{ pkg.module }}``
^^^^{{ "^" * len(pkg.module) }}

.. automodule:: {{ pkg.module }}

{% for rule in rules %}
- :class:`{{rule.__name__}}`
{% endfor %}

{% for rule in rules %}
.. class:: {{ rule.__name__ }}
{{ rule.__doc__.rstrip() }}

{% if rule.MESSAGE %}
    .. attribute:: MESSAGE

{{ redent(rule.MESSAGE, "        ") }}

{% endif %}
{% if rule.AUTOFIX %}
    .. attribute:: AUTOFIX
        :type: Yes

{% endif %}
{% if rule.PYTHON_VERSION %}
    .. attribute:: PYTHON_VERSION
        :type: {{ repr(rule.PYTHON_VERSION) }}
{% endif %}

    .. attribute:: VALID

{% for case in rule.VALID[:2] %}
        .. code:: python

{{ redent(case.code, "            ") }}
{% endfor %}

    .. attribute:: INVALID

{% for case in rule.INVALID[:2] %}
        .. code:: python

{{ redent(case.code, "            ") }}
{% if case.expected_replacement %}

            # suggested fix
{{ redent(case.expected_replacement, "            ") }}

{% endif %}
{% endfor %}
{% endfor %}
{% endfor %}
    """,
    trim_blocks=True,
    lstrip_blocks=True,
)


def redent(value: str, prefix: str = "") -> str:
    return indent(dedent(value).strip("\n"), prefix).rstrip()


def main() -> None:
    qrules = sorted(QualifiedRule(r) for r in RULES)
    packages = {qrule: list(find_rules(qrule)) for qrule in qrules}

    RULES_DOC.write_text(
        PAGE_TPL.render(
            dedent=dedent,
            indent=indent,
            redent=redent,
            hasattr=hasattr,
            len=len,
            repr=repr,
            packages=packages,
        )
    )


if __name__ == "__main__":
    main()
