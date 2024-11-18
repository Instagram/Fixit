# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import threading
from functools import partial
from pathlib import Path
from typing import Any, Callable, cast, Dict, Generator, List, Optional, TypeVar

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
from pygls.workspace.text_document import TextDocument

from .__version__ import __version__
from .api import fixit_bytes
from .config import generate_config
from .ftypes import Config, FileContent, LSPOptions, Options, Result
from .util import capture


class LSP:
    """
    Server for the Language Server Protocol.
    Provides diagnostics as you type, and exposes a formatter.
    https://microsoft.github.io/language-server-protocol/
    """

    def __init__(self, fixit_options: Options, lsp_options: LSPOptions) -> None:
        self.fixit_options = fixit_options
        self.lsp_options = lsp_options

        self._config_cache: Dict[Path, Config] = {}

        # separate debounce timer per URI so that linting one URI
        # doesn't cancel linting another
        self._validate_uri: Dict[str, Callable[[int], None]] = {}

        self.lsp = LanguageServer("fixit-lsp", __version__)
        # `partial` since `pygls` can register functions but not methods
        self.lsp.feature(TEXT_DOCUMENT_DID_OPEN)(partial(self.on_did_open))
        self.lsp.feature(TEXT_DOCUMENT_DID_CHANGE)(partial(self.on_did_change))
        self.lsp.feature(TEXT_DOCUMENT_FORMATTING)(partial(self.format))

    def load_config(self, path: Path) -> Config:
        """
        Cached fetch of fixit.toml(s) for fixit_bytes.
        """
        if path not in self._config_cache:
            self._config_cache[path] = generate_config(path, options=self.fixit_options)
        return self._config_cache[path]

    def diagnostic_generator(
        self, uri: str, autofix: bool = False
    ) -> Generator[Result, bool, Optional[FileContent]] | None:
        """
        LSP wrapper (provides document state from `pygls`) for `fixit_bytes`.
        """
        path = Uri.to_fs_path(uri)
        if not path:
            return None
        path = Path(path)

        doc: TextDocument = self.lsp.workspace.get_document(uri)  # type: ignore[no-untyped-call]
        return fixit_bytes(
            path,
            doc.source.encode(),
            autofix=autofix,
            config=self.load_config(path),
        )

    def _validate(self, uri: str, version: int) -> None:
        """
        Effect: publishes Fixit diagnostics to the LSP client.
        """
        generator = self.diagnostic_generator(uri)
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
        self.lsp.publish_diagnostics(uri, diagnostics, version=version)

    def validate(self, uri: str, version: int) -> None:
        """
        Effect: may publish Fixit diagnostics to the LSP client after a debounce delay.
        """
        if uri not in self._validate_uri:
            self._validate_uri[uri] = debounce(self.lsp_options.debounce_interval)(
                partial(self._validate, uri)
            )
        self._validate_uri[uri](version)

    def on_did_open(self, params: DidOpenTextDocumentParams) -> None:
        self.validate(params.text_document.uri, params.text_document.version)

    def on_did_change(self, params: DidChangeTextDocumentParams) -> None:
        self.validate(params.text_document.uri, params.text_document.version)

    def format(self, params: DocumentFormattingParams) -> List[TextEdit] | None:
        generator = self.diagnostic_generator(params.text_document.uri, autofix=True)
        if generator is None:
            return None

        captured = capture(generator)
        for _ in captured:
            pass
        formatted_content = captured.result
        if not formatted_content:
            return None

        doc: TextDocument = self.lsp.workspace.get_document(params.text_document.uri)  # type: ignore[no-untyped-call]
        entire_range = Range(
            start=Position(line=0, character=0),
            end=Position(line=len(doc.lines) - 1, character=len(doc.lines[-1])),
        )

        return [TextEdit(new_text=formatted_content.decode(), range=entire_range)]

    def start(self) -> None:
        """
        Effect: occupies the specified I/O channels.
        """
        if self.lsp_options.ws:
            self.lsp.start_ws("localhost", self.lsp_options.ws)
        if self.lsp_options.tcp:
            self.lsp.start_tcp("localhost", self.lsp_options.tcp)
        if self.lsp_options.stdio:
            self.lsp.start_io()


VoidFunction = TypeVar("VoidFunction", bound=Callable[..., None])


class Debouncer:
    def __init__(self, f: Callable[..., Any], interval: float) -> None:
        self.f = f
        self.interval = interval
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.interval, self.f, args, kwargs)
            self._timer.start()


def debounce(interval: float) -> Callable[[VoidFunction], VoidFunction]:
    """
    Wait `interval` seconds before calling `f`, and cancel if called again.
    The decorated function will return None immediately,
    ignoring the delayed return value of `f`.
    """

    def decorator(f: VoidFunction) -> VoidFunction:
        if interval <= 0:
            return f
        return cast(VoidFunction, Debouncer(f, interval))

    return decorator
