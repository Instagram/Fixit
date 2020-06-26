# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import json
from pathlib import Path

from libcst.metadata.type_inference_provider import (
    PyreData,
    _process_pyre_data,
    run_command,
)


def generate_types(source_path: str, output_path: Path) -> None:
    print("Starting pyre server")
    stdout: str
    stderr: str
    return_code: int

    stdout, stderr, return_code = run_command("pyre start")
    if return_code != 0:
        print(stdout)
        print(stderr)
    else:
        cmd = f'''pyre query "types(path='{source_path}')"'''
        stdout, stderr, return_code = run_command(cmd)
        if return_code != 0:
            print(stdout)
            print(stderr)
        else:
            data = json.loads(stdout)
            data = data["response"][0]
            data: PyreData = _process_pyre_data(data)
            print(f"Writing output to {output_path}")
            output_path.write_text(json.dumps({"types": data["types"]}, indent=2))


if __name__ == "__main__":
    """
    Run this script directly to generate pyre data for lint rule test cases.
    You may paste the test case code into a temporary file and provide the path to this file in `source_path`.
    """
    parser = argparse.ArgumentParser(
        description="Generate json file of type information from source code using `pyre query`."
    )
    parser.add_argument("--source_path", help="Path to source code.", required=True)
    parser.add_argument(
        "--output_path",
        help="Path to .json file into which to dump type data.",
        required=True,
    )

    args: argparse.Namespace = parser.parse_args()
    output_path: Path = Path(args.output_path)
    generate_types(args.source_path, output_path)
