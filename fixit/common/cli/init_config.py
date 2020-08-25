# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import sys

from fixit.common.config import gen_config_file


if __name__ == "__main__":
    """
    Generate a `fixit.config.yaml` file with defaults in the current working directory.
    """
    gen_config_file()
    sys.exit(0)
