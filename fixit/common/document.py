# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import difflib
from pathlib import Path
from textwrap import dedent, indent
from typing import Union

from fixit.common.base import LintRuleT
from fixit.common.config import get_rules_from_config
from fixit.common.utils import InvalidTestCase, ValidTestCase


def _add_code_indent(code: str) -> str:
    return indent(code, "    ") + "\n"


def _add_reference_label(label: str) -> str:
    return f".. _{label}:\n"


def _add_title_style(title: str, symbol: str) -> str:
    title_length = len(title)
    return dedent(
        f"""
            {symbol * title_length}
            {title}
            {symbol * title_length}
            """
    )


def _get_example(example: Union[ValidTestCase, InvalidTestCase], index: int) -> str:
    s = ""
    source = dedent(example.code)
    s += dedent(
        f"""
        # {index + 1}:

        .. code-block:: python

        """
    )
    s += _add_code_indent(source)
    if isinstance(example, InvalidTestCase):
        replacement = example.expected_replacement
        if replacement is not None:
            autofix = dedent(replacement)
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


def gen_example_cases(rule: LintRuleT, key: str, to_fold_examples: bool = True) -> str:
    s = ""
    examples_before_folding = 3
    if hasattr(rule, key):
        s += _add_title_style(f"{key} Code Examples", "-")
        for idx, example in enumerate(getattr(rule, key)):
            if to_fold_examples and idx >= examples_before_folding:
                if idx == examples_before_folding:
                    s += ".. container:: toggle\n\n"
                s += _add_code_indent(_get_example(example, idx))
            else:
                s += _get_example(example, idx)

    return s


def _has_autofix(rule: LintRuleT) -> bool:
    invalids = getattr(rule, "INVALID", [])
    return any(i.expected_replacement for i in invalids)


def create_rule_doc(directory: Path, to_fold_examples: bool = False) -> None:
    directory.mkdir(exist_ok=True)
    for rule in get_rules_from_config():
        rule_name = rule.__name__
        with (directory / f"{rule_name}.rst").open("w") as fp:
            fp.write(_add_reference_label(rule_name))
            fp.write(_add_title_style(rule_name, "="))
            doc = rule.__doc__
            if doc is not None:
                fp.write(dedent(doc))
            message = getattr(rule, "MESSAGE", None)
            if message is not None:
                fp.write(_add_title_style("Message", "-"))
                fp.write(message + "\n")
            fp.write(
                _add_title_style(
                    f"Has Autofix: {'Yes' if _has_autofix(rule) else 'No'}", "-"
                )
            )
            fp.write(gen_example_cases(rule, "VALID", to_fold_examples))
            fp.write(gen_example_cases(rule, "INVALID", to_fold_examples))
