# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import json
import tempfile
from pathlib import Path
from typing import cast

from libcst.metadata import TypeInferenceProvider
from libcst.metadata.type_inference_provider import (
    PyreData,
    _process_pyre_data,
    run_command,
)

from fixit.common.base import CstLintRule, LintRuleT
from fixit.common.cli.args import (
    _get_fixture_dir,
    get_pyre_fixture_dir_parser,
    get_rule_parser,
    get_rules_package_parser,
)
from fixit.common.config import FIXTURE_DIRECTORY
from fixit.common.utils import _dedent


class RuleNotTypeDependentError(Exception):
    pass


class RuleTypeError(Exception):
    pass


def gen_types_for_test_case(source_code: str, dest_path: Path) -> None:
    rule_fixture_subdir: Path = dest_path.parent
    if not rule_fixture_subdir.exists():
        rule_fixture_subdir.mkdir(parents=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=rule_fixture_subdir, suffix=".py"
    ) as temp:
        temp.write(_dedent(source_code))
        temp.seek(0)

        cmd = f'''pyre query "types(path='{temp.name}')"'''
        stdout, stderr, return_code = run_command(cmd)
        if return_code != 0:
            print(stdout)
            print(stderr)
        else:
            data = json.loads(stdout)
            data = data["response"][0]
            data: PyreData = _process_pyre_data(data)
            print(f"Writing output to {dest_path}")
            dest_path.write_text(json.dumps({"types": data["types"]}, indent=2))


def gen_types(rule: CstLintRule, rule_fixture_dir: Path) -> None:
    if TypeInferenceProvider not in rule.get_inherited_dependencies():
        raise RuleNotTypeDependentError(
            "Rule does not list TypeInferenceProvider in its `METADATA_DEPENDENCIES`."
        )
    if hasattr(rule, "VALID") or hasattr(rule, "INVALID"):
        print("Starting pyre server")

        stdout, stderr, return_code = run_command("pyre start")
        if return_code != 0:
            print(stdout)
            print(stderr)
        else:
            class_name = getattr(rule, "__name__")
            if hasattr(rule, "VALID"):
                for idx, valid_tc in enumerate(getattr(rule, "VALID")):
                    path: Path = rule_fixture_dir / f"{class_name}_VALID_{idx}.json"
                    gen_types_for_test_case(source_code=valid_tc.code, dest_path=path)
            if hasattr(rule, "INVALID"):
                for idx, invalid_tc in enumerate(getattr(rule, "INVALID")):
                    path: Path = rule_fixture_dir / f"{class_name}_INVALID_{idx}.json"
                    gen_types_for_test_case(source_code=invalid_tc.code, dest_path=path)
            run_command("pyre stop")


def get_fixture_path(
    fixture_top_dir: Path, rule_module: str, rules_package: str
) -> Path:
    subpackage: str = rule_module.split(f"{rules_package}.", 1)[-1]
    fixture_subdir = Path(subpackage.replace(".", "/"))
    return fixture_top_dir / fixture_subdir


if __name__ == "__main__":
    """
    Run this script directly to generate pyre data for a lint rule that requires TypeInferenceProvider metadata.
    """
    parser = argparse.ArgumentParser(
        description="Generate fixture files required to run unit tests on `TypeInference`-dependent lint rules.",
        parents=[
            get_rule_parser(),
            get_pyre_fixture_dir_parser(),
            get_rules_package_parser(),
        ],
    )
    args: argparse.Namespace = parser.parse_args()
    rule: LintRuleT = args.rule
    fixture_dir: Path = (
        Path(args.fixture_dir)
        if args.fixture_dir is not None
        else _get_fixture_dir(FIXTURE_DIRECTORY)
    )
    fixture_path: Path = get_fixture_path(
        fixture_dir, rule.__module__, args.rules_package
    )
    if not issubclass(rule, CstLintRule):
        raise RuleTypeError("Rule must inherit from CstLintRule.")
    gen_types(cast(CstLintRule, rule), fixture_path)
