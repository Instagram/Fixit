#!/bin/bash

# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

set -eu

die() { echo "$1"; exit 1; }

while read filename; do \
    if [ -f "$filename" ]; then
        grep -q "^# Copyright (c) Meta Platforms, Inc. and affiliates." "$filename" ||
            die "Missing copyright in $filename"
    fi
done < <( git ls-tree -r --name-only HEAD | grep "\(.py\|\.sh\)$" )

