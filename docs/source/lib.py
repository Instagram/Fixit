# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import difflib
from pathlib import Path
from textwrap import dedent, indent
from typing import IO

from fixit.common.base import LintRuleT
from fixit.rule_lint_engine import get_rules


def _add_code_indent(code: str) -> str:
    return indent(code, "    ") + "\n"


def write_example_cases(fp: IO[str], rule: LintRuleT, key: str) -> None:
    s = ""
    doc = rule.__doc__
    if doc:
        s += dedent(doc)
    if hasattr(rule, key):
        line = f"{key} Code Examples"
        line_len = len(line)
        s += dedent(
            f"""
            {"-" * line_len}
            {line}
            {"-" * line_len}
            """
        )
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
    fp.write(s)


def _get_dashed_rule_name_from_camel_case(name: str) -> str:
    """E.g. convert "ClsInClassmethodRule" as "cls-in-classmethod". """
    rule_name = "".join(f"-{i.lower()}" if i.isupper() else i for i in name).lstrip("-")
    post_fix_to_remove = "-rule"
    if rule_name.endswith(post_fix_to_remove):
        rule_name = rule_name[: -len(post_fix_to_remove)]
    return rule_name


def create_rule_doc() -> None:
    directory = Path(__file__).parent / "rules"
    directory.mkdir(exist_ok=True)

    for rule in get_rules():
        rule_name = _get_dashed_rule_name_from_camel_case(rule.__name__)
        rule_name_len = len(rule_name)
        with (directory / f"{rule_name}.rst").open("w") as fp:
            fp.write(
                dedent(
                    f"""\
                    {"=" * rule_name_len}
                    {rule_name}
                    {"=" * rule_name_len}
                    """
                )
            )
            write_example_cases(fp, rule, "VALID")
            write_example_cases(fp, rule, "INVALID")
