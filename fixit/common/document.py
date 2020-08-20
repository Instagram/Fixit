# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import difflib
from pathlib import Path
from textwrap import dedent, indent

from fixit.common.base import LintRuleT
from fixit.common.config import get_rules_from_config


def _add_code_indent(code: str) -> str:
    return indent(code, "    ") + "\n"


def _add_title_style(title: str, symbol: str) -> str:
    title_length = len(title)
    return dedent(
        f"""
            {symbol * title_length}
            {title}
            {symbol * title_length}
            """
    )


def gen_example_cases(rule: LintRuleT, key: str) -> str:
    s = ""
    if hasattr(rule, key):
        s += _add_title_style(f"{key} Code Examples", "-")
        for idx, example in enumerate(getattr(rule, key)):
            source = dedent(example.code)
            s += dedent(
                f"""
                # {idx + 1}:

                .. code-block:: python

                """
            )
            s += _add_code_indent(source)
            if (
                hasattr(example, "expected_replacement")
                and example.expected_replacement is not None
            ):
                autofix = dedent(example.expected_replacement)
                diff = "\n".join(
                    difflib.unified_diff(
                        source.splitlines(), autofix.splitlines(), lineterm=""
                    )
                )
                s += dedent(
                    """
                    Autofix:

                    .. code-block:: python

                    """
                )
                s += _add_code_indent(diff)
    return s


def create_rule_doc(directory: Path) -> None:
    directory.mkdir(exist_ok=True)

    for rule in get_rules_from_config():
        rule_name = rule.__name__
        with (directory / f"{rule_name}.rst").open("w") as fp:
            fp.write(_add_title_style(rule_name, "="))
            doc = rule.__doc__
            if doc:
                fp.write(dedent(doc))
            fp.write(gen_example_cases(rule, "VALID"))
            fp.write(gen_example_cases(rule, "INVALID"))
