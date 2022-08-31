# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
For backwards compatibility.
"""

from fixit.cli import find_files, ipc_main, IPCResult, LintOpts, map_paths


__all__ = ["IPCResult", "LintOpts", "find_files", "ipc_main", "map_paths"]
