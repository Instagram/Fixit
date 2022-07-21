# Copyright (c) Meta Platforms, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import click

from fixit import __version__


@click.group()
@click.pass_context
@click.version_option(__version__, "--version", "-V", prog_name="fixit")
def main():
    pass
