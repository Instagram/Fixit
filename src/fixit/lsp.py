# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path
from typing import Dict

import pygls.uris as Uri

from lsprotocol.types import (
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    DocumentFormattingParams,
    Position,
    Range,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_FORMATTING,
    TextEdit,
)
from pygls.server import LanguageServer

from fixit import __version__
from fixit.util import capture

from .api import fixit_bytes
from .config import generate_config
from .ftypes import Config, LspOptions, Options


def warm_config_cache(
    config_cache: Dict[Path, Config], path: Path, options: Options, bust=False
):
    if bust or (path not in config_cache):
        config_cache[path] = generate_config(path, options=options)


def start_lsp(main_options: Options, lsp_options: LspOptions):
    ls = LanguageServer("fixit-lsp", __version__)
    config_cache: Dict[Path, Config] = {}

    def diagnostic_generator(uri: str, autofix=False):
        path = Uri.to_fs_path(uri)
        if not path:
            return None
        path = Path(path)

        warm_config_cache(config_cache, path, options=main_options)
        return fixit_bytes(
            path,
            ls.workspace.get_document(uri).source.encode(),
            autofix=autofix,
            config=config_cache[path],
        )

    def publish_diagnostics(uri: str, version=None):
        generator = diagnostic_generator(uri)
        if not generator:
            return
        diagnostics = []
        for result in generator:
            violation = result.violation
            if not violation:
                continue
            diagnostic = Diagnostic(
                Range(
                    Position(  # LSP is 0-indexed; fixit line numbers are 1-indexed
                        violation.range.start.line - 1, violation.range.start.column
                    ),
                    Position(violation.range.end.line - 1, violation.range.end.column),
                ),
                violation.message,
                severity=DiagnosticSeverity.Warning,
                code=violation.rule_name,
                source="fixit",
            )
            diagnostics.append(diagnostic)
        ls.publish_diagnostics(uri, diagnostics, version=version)

    @ls.feature(TEXT_DOCUMENT_DID_OPEN)
    def _(params: DidOpenTextDocumentParams):
        publish_diagnostics(
            params.text_document.uri, version=params.text_document.version
        )

    @ls.feature(TEXT_DOCUMENT_DID_CHANGE)
    def _(params: DidChangeTextDocumentParams):
        publish_diagnostics(
            params.text_document.uri, version=params.text_document.version
        )

    @ls.feature(TEXT_DOCUMENT_FORMATTING)
    def _(params: DocumentFormattingParams):
        generator = diagnostic_generator(params.text_document.uri, autofix=True)
        if generator is None:
            return None

        captured = capture(generator)
        for _ in captured:
            pass
        formatted_content = captured.result
        if not formatted_content:
            return None

        doc = ls.workspace.get_document(params.text_document.uri)
        entire_range = Range(
            start=Position(line=0, character=0),
            end=Position(line=len(doc.lines) - 1, character=len(doc.lines[-1])),
        )

        return [TextEdit(new_text=formatted_content.decode(), range=entire_range)]

    if lsp_options.stdio:
        ls.start_io()
    if lsp_options.tcp:
        ls.start_tcp("localhost", lsp_options.tcp)
    if lsp_options.ws:
        ls.start_ws("localhost", lsp_options.ws)
