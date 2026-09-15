# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import threading
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    Generator,
    List,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import pygls.uris as Uri
from libcst import CSTNode, Decorator, Module
from libcst.metadata import (
    CodeRange,
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
)
from lsprotocol.types import (
    CodeAction,
    CodeActionContext,
    CodeActionKind,
    CodeActionOptions,
    CodeActionParams,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    DocumentFormattingParams,
    Position,
    PublishDiagnosticsParams,
    Range,
    TEXT_DOCUMENT_CODE_ACTION,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_FORMATTING,
    TextEdit,
    WorkspaceEdit,
)
from pygls.lsp.server import LanguageServer
from pygls.workspace.text_document import TextDocument

from .__version__ import __version__
from .api import fixit_bytes
from .config import collect_rules, generate_config
from .engine import LintRunner
from .format import format_module
from .ftypes import Config, FileContent, LintViolation, LSPOptions, Options, Result
from .util import capture

LOG = logging.getLogger(__name__)

IGNORE_DIRECTIVES = ("lint-fixme", "lint-ignore")
"""Suppression directives offered as code actions, in the order they are offered."""


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
        self.lsp.feature(
            TEXT_DOCUMENT_CODE_ACTION,
            CodeActionOptions(code_action_kinds=[CodeActionKind.QuickFix]),
        )(partial(self.code_action))

    def load_config(self, path: Path) -> Config:
        """
        Cached fetch of fixit.toml(s) for fixit_bytes.
        """
        if path not in self._config_cache:
            self._config_cache[path] = generate_config(path, options=self.fixit_options)
        return self._config_cache[path]

    def diagnostic_generator(
        self, uri: str, autofix: bool = False
    ) -> Optional[Generator[Result, bool, Optional[FileContent]]]:
        """
        LSP wrapper (provides document state from `pygls`) for `fixit_bytes`.
        """
        path_uri = Uri.to_fs_path(uri)
        if not path_uri:
            return None
        path = Path(path_uri)

        doc: TextDocument = self.lsp.workspace.get_text_document(uri)  # type: ignore[no-untyped-call]
        return fixit_bytes(
            path,
            doc.source.encode(),
            autofix=autofix,
            config=self.load_config(path),
        )

    def lint_document(self, uri: str) -> Optional["LintDocument"]:
        """
        Lint the current in-memory contents of ``uri``, keeping the parsed module.

        Unlike :meth:`diagnostic_generator`, this retains the :class:`LintRunner` so
        that individual autofixes can be applied afterwards, and so that the module
        can be re-inspected while building code actions.
        """
        path_uri = Uri.to_fs_path(uri)
        if not path_uri:
            return None
        path = Path(path_uri)

        doc: TextDocument = self.lsp.workspace.get_text_document(uri)  # type: ignore[no-untyped-call]
        config = self.load_config(path)
        try:
            rules = collect_rules(config)
            if not rules:
                return None
            runner = LintRunner(path, doc.source.encode())
            violations = list(runner.collect_violations(rules, config))
        except Exception as error:
            # parity with `fixit_bytes`, which reports exceptions as results that
            # the LSP has no way to surface to the client
            LOG.debug("Exception while linting %s", uri, exc_info=error)
            return None

        return LintDocument(path, config, doc, runner, violations)

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
            diagnostics.append(diagnostic(violation))
        self.lsp.text_document_publish_diagnostics(
            PublishDiagnosticsParams(uri, diagnostics, version)
        )

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

    def format(self, params: DocumentFormattingParams) -> Optional[List[TextEdit]]:
        generator = self.diagnostic_generator(params.text_document.uri, autofix=True)
        if generator is None:
            return None

        captured = capture(generator)
        for _ in captured:
            pass
        formatted_content = captured.result
        if not formatted_content:
            return None

        doc: TextDocument = self.lsp.workspace.get_text_document(
            params.text_document.uri
        )

        return text_edits(doc.source, formatted_content.decode())

    def code_action(self, params: CodeActionParams) -> Optional[List[CodeAction]]:
        """
        Offer quickfixes for every violation overlapping the requested range.

        Each violation with an autofix gets an "apply this one fix" action, and every
        violation gets actions inserting a ``# lint-fixme`` or ``# lint-ignore``
        suppression comment.
        """
        uri = params.text_document.uri
        if not wants_kind(params.context, CodeActionKind.QuickFix):
            return None

        document = self.lint_document(uri)
        if document is None:
            return None

        actions: List[CodeAction] = []
        for violation in document.violations:
            if not ranges_intersect(params.range, lsp_range(violation.range)):
                continue

            found = diagnostic(violation)
            if violation.autofixable:
                edits = document.autofix_edits(violation)
                if edits:
                    actions.append(
                        quickfix(
                            f"Fix {violation.rule_name}",
                            uri,
                            edits,
                            found,
                            preferred=True,
                        )
                    )

            for directive in IGNORE_DIRECTIVES:
                edits = document.suppression_edits(violation, directive)
                if edits:
                    actions.append(
                        quickfix(
                            f"Silence {violation.rule_name} with # {directive}",
                            uri,
                            edits,
                            found,
                        )
                    )

        return actions

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


@dataclass
class LintDocument:
    """
    A single linted document, with everything needed to build code actions for it.
    """

    path: Path
    config: Config
    doc: TextDocument
    runner: LintRunner
    violations: List[LintViolation]

    def __post_init__(self) -> None:
        self._metadata: Optional[
            Tuple[Mapping[CSTNode, CodeRange], Mapping[CSTNode, CSTNode]]
        ] = None

    def autofix_edits(self, violation: LintViolation) -> List[TextEdit]:
        """
        Edits applying the autofix for exactly this violation, and nothing else.

        The replacement is applied to the parsed module and the result is formatted
        the same way ``fixit fix`` would, rather than splicing the replacement node
        into the reported range: a rule may report a position that doesn't cover the
        node being replaced, and the configured formatter may reflow the result.
        """
        if not violation.autofixable:
            return []
        try:
            updated = self.runner.apply_replacements([violation])
            content = format_module(updated, self.path, self.config)
        except Exception as error:
            LOG.debug(
                "Exception while applying %s", violation.rule_name, exc_info=error
            )
            return []
        return text_edits(self.doc.source, content.decode())

    def suppression_edits(
        self, violation: LintViolation, directive: str
    ) -> List[TextEdit]:
        """
        Edits inserting a ``# <directive>: RuleName`` comment above the violation.

        The comment is anchored to the innermost enclosing node that owns leading
        comment lines, which is where :meth:`~fixit.LintRule.ignore_lint` looks for
        suppression directives. Anchoring to the reported line instead would put the
        comment inside a bracketed expression for any multi-line statement, where it
        would be silently ignored.
        """
        anchor = self.suppression_anchor(violation)
        if anchor is None:
            return []

        line, indent = anchor
        newline = self.runner.module.default_newline
        return [
            TextEdit(
                range=Range(
                    start=Position(line=line, character=0),
                    end=Position(line=line, character=0),
                ),
                new_text=f"{indent}# {directive}: {violation.rule_name}{newline}",
            )
        ]

    def suppression_anchor(self, violation: LintViolation) -> Optional[Tuple[int, str]]:
        """
        Zero-indexed line and indentation to insert a suppression comment before.
        """
        positions, parents = self.metadata()

        node: Optional[CSTNode] = violation.node
        while node is not None and not isinstance(node, Module):
            leading_lines = getattr(node, "leading_lines", None)
            # mirror `LintRule.node_comments`, which stops looking for directives at
            # the first non-decorator ancestor owning leading comment lines
            if leading_lines is not None and not isinstance(node, Decorator):
                break
            node = parents.get(node)

        if node is None or isinstance(node, Module):
            # a violation on the module itself is suppressed by the module header
            return 0, ""

        position = positions.get(node)
        if position is None:
            return None

        line = position.start.line - 1  # LSP is 0-indexed; libcst is 1-indexed
        try:
            text = self.doc.lines[line]
        except IndexError:  # pragma: no cover - only if positions disagree with text
            return None
        return line, text[: len(text) - len(text.lstrip())]

    def metadata(
        self,
    ) -> Tuple[Mapping[CSTNode, CodeRange], Mapping[CSTNode, CSTNode]]:
        """
        Lazily resolved node positions and parents, for the already-parsed module.
        """
        if self._metadata is None:
            wrapper = MetadataWrapper(self.runner.module, unsafe_skip_copy=True)
            resolved = wrapper.resolve_many([PositionProvider, ParentNodeProvider])
            self._metadata = (
                cast(Mapping[CSTNode, CodeRange], resolved[PositionProvider]),
                cast(Mapping[CSTNode, CSTNode], resolved[ParentNodeProvider]),
            )
        return self._metadata


def lsp_range(code_range: CodeRange) -> Range:
    """
    Convert a libcst :class:`CodeRange` to an LSP :class:`Range`.
    """
    return Range(
        # LSP is 0-indexed; fixit line numbers are 1-indexed
        Position(code_range.start.line - 1, code_range.start.column),
        Position(code_range.end.line - 1, code_range.end.column),
    )


def diagnostic(violation: LintViolation) -> Diagnostic:
    """
    Convert a :class:`LintViolation` to an LSP :class:`Diagnostic`.
    """
    return Diagnostic(
        lsp_range(violation.range),
        violation.message,
        severity=DiagnosticSeverity.Warning,
        code=violation.rule_name,
        source="fixit",
    )


def quickfix(
    title: str,
    uri: str,
    edits: List[TextEdit],
    found: Diagnostic,
    preferred: bool = False,
) -> CodeAction:
    """
    Build a quickfix :class:`CodeAction` applying ``edits`` to ``uri``.
    """
    return CodeAction(
        title=title,
        kind=CodeActionKind.QuickFix,
        diagnostics=[found],
        edit=WorkspaceEdit(changes={uri: edits}),
        is_preferred=preferred or None,
    )


def wants_kind(context: CodeActionContext, kind: Union[CodeActionKind, str]) -> bool:
    """
    Whether a code action request asked for ``kind``, honoring the LSP kind hierarchy.
    """
    if not context.only:
        return True
    return any(kind == only or kind.startswith(f"{only}.") for only in context.only)


def ranges_intersect(first: Range, second: Range) -> bool:
    """
    Whether two LSP ranges overlap, counting zero-width ranges that merely touch.
    """

    def key(position: Position) -> Tuple[int, int]:
        return position.line, position.character

    return key(first.start) <= key(second.end) and key(second.start) <= key(first.end)


def text_edits(before: str, after: str) -> List[TextEdit]:
    """
    A minimal list of :class:`TextEdit`\\ s turning ``before`` into ``after``.

    Only the span of lines that actually changed is replaced, so that clients keep
    cursors, folds, and decorations outside of that span.
    """
    if before == after:
        return []

    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)

    prefix = 0
    while (
        prefix < len(before_lines)
        and prefix < len(after_lines)
        and before_lines[prefix] == after_lines[prefix]
    ):
        prefix += 1

    suffix = 0
    while (
        suffix < len(before_lines) - prefix
        and suffix < len(after_lines) - prefix
        and before_lines[-1 - suffix] == after_lines[-1 - suffix]
    ):
        suffix += 1

    end_line = len(before_lines) - suffix
    if end_line < len(before_lines):
        end = Position(line=end_line, character=0)
    else:
        # the last line of the document changed, and it may not end in a newline,
        # so end the range at the last character rather than at a line that the
        # client doesn't have
        end = Position(
            line=max(len(before_lines) - 1, 0),
            character=len(before_lines[-1]) if before_lines else 0,
        )

    return [
        TextEdit(
            range=Range(start=Position(line=prefix, character=0), end=end),
            new_text="".join(after_lines[prefix : len(after_lines) - suffix]),
        )
    ]


VoidFunction = TypeVar("VoidFunction", bound=Callable[..., None])


class Debouncer:
    def __init__(self, f: Callable[..., Any], interval: float) -> None:
        self.f = f
        self.interval = interval
        self._timer: Optional[threading.Timer] = None
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
