# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator, List, Optional, Sequence, Tuple

import pygls.uris as Uri

from lsprotocol.types import (
    CodeAction,
    CodeActionContext,
    CodeActionKind,
    CodeActionParams,
    DocumentFormattingParams,
    FormattingOptions,
    Position,
    Range,
    TextDocumentIdentifier,
    TextDocumentItem,
    TextEdit,
)
from pygls.workspace import Workspace

from fixit.ftypes import LSPOptions, Options
from fixit.lsp import LSP, ranges_intersect, text_edits, wants_kind


def apply_edits(source: str, edits: Sequence[TextEdit]) -> str:
    """
    Apply LSP text edits to a document, the way a client would.
    """
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def offset(position: Position) -> int:
        return offsets[min(position.line, len(lines))] + position.character

    result = source
    for edit in sorted(edits, key=lambda e: offset(e.range.start), reverse=True):
        result = (
            result[: offset(edit.range.start)]
            + edit.new_text
            + result[offset(edit.range.end) :]
        )
    return result


class LspTest(unittest.TestCase):
    maxDiff = None

    @contextmanager
    def document(self, source: str) -> Generator[Tuple[LSP, str], None, None]:
        """
        An LSP server with ``source`` open, in a directory with no fixit config.
        """
        server = LSP(
            Options(),
            LSPOptions(tcp=None, ws=None, stdio=False, debounce_interval=0),
        )
        # the workspace is normally created while handling `initialize`
        server.lsp.protocol._workspace = Workspace(None)
        with TemporaryDirectory() as tdp:
            uri = Uri.from_fs_path(str(Path(tdp).resolve() / "sample.py"))
            assert uri is not None
            server.lsp.workspace.put_text_document(
                TextDocumentItem(uri=uri, language_id="python", version=1, text=source)
            )
            yield server, uri

    def code_actions(
        self,
        source: str,
        line: int,
        column: int = 0,
        end: Optional[Position] = None,
        only: Optional[Sequence[str]] = None,
    ) -> Tuple[List[CodeAction], str]:
        """
        Request code actions at a position, and return them with the document uri.
        """
        with self.document(source) as (server, uri):
            start = Position(line=line, character=column)
            params = CodeActionParams(
                text_document=TextDocumentIdentifier(uri=uri),
                range=Range(start=start, end=end or start),
                context=CodeActionContext(diagnostics=[], only=only),
            )
            return server.code_action(params) or [], uri

    def edits_for(self, action: CodeAction, uri: str) -> List[TextEdit]:
        self.assertIsNotNone(action.edit)
        assert action.edit is not None and action.edit.changes is not None
        return list(action.edit.changes[uri])

    def lint(self, source: str) -> List[str]:
        """
        Rule names reported for ``source``, via the same path the LSP uses.
        """
        with self.document(source) as (server, uri):
            document = server.lint_document(uri)
            assert document is not None
            return [violation.rule_name for violation in document.violations]


class TextEditsTest(unittest.TestCase):
    def test_no_change(self) -> None:
        self.assertEqual([], text_edits("x = 1\n", "x = 1\n"))

    def test_middle_line(self) -> None:
        before = "a = 1\nb = 2\nc = 3\n"
        after = "a = 1\nb = 22\nc = 3\n"
        edits = text_edits(before, after)
        self.assertEqual(
            [
                TextEdit(
                    range=Range(Position(1, 0), Position(2, 0)),
                    new_text="b = 22\n",
                )
            ],
            edits,
        )
        self.assertEqual(after, apply_edits(before, edits))

    def test_last_line_without_trailing_newline(self) -> None:
        before = "a = 1\nb = 2"
        after = "a = 1\nb = 22"
        edits = text_edits(before, after)
        self.assertEqual(Position(1, 5), edits[0].range.end)
        self.assertEqual(after, apply_edits(before, edits))

    def test_appends_trailing_newline(self) -> None:
        before = "a = 1"
        after = "a = 1\n"
        self.assertEqual(after, apply_edits(before, text_edits(before, after)))

    def test_empty_document(self) -> None:
        self.assertEqual("x\n", apply_edits("", text_edits("", "x\n")))

    def test_deletes_lines(self) -> None:
        before = "a = 1\nb = 2\nc = 3\n"
        after = "a = 1\n"
        self.assertEqual(after, apply_edits(before, text_edits(before, after)))


class RangesIntersectTest(unittest.TestCase):
    def test_overlap(self) -> None:
        first = Range(Position(1, 4), Position(1, 10))
        self.assertTrue(ranges_intersect(first, Range(Position(1, 6), Position(1, 8))))
        self.assertTrue(ranges_intersect(first, Range(Position(0, 0), Position(5, 0))))

    def test_cursor_at_edges(self) -> None:
        first = Range(Position(1, 4), Position(1, 10))
        for cursor in (Position(1, 4), Position(1, 10)):
            with self.subTest(cursor=cursor):
                self.assertTrue(ranges_intersect(Range(cursor, cursor), first))

    def test_disjoint(self) -> None:
        first = Range(Position(1, 4), Position(1, 10))
        self.assertFalse(ranges_intersect(first, Range(Position(2, 0), Position(2, 1))))
        self.assertFalse(ranges_intersect(first, Range(Position(1, 0), Position(1, 3))))


class WantsKindTest(unittest.TestCase):
    def test_no_filter(self) -> None:
        context = CodeActionContext(diagnostics=[])
        self.assertTrue(wants_kind(context, CodeActionKind.QuickFix))

    def test_matching_and_parent_kinds(self) -> None:
        for only in (["quickfix"], ["quickfix", "source"], ["quickfix.foo"]):
            with self.subTest(only=only):
                context = CodeActionContext(diagnostics=[], only=only)
                self.assertEqual(
                    only != ["quickfix.foo"],
                    wants_kind(context, CodeActionKind.QuickFix),
                )

    def test_other_kinds(self) -> None:
        context = CodeActionContext(diagnostics=[], only=["source.organizeImports"])
        self.assertFalse(wants_kind(context, CodeActionKind.QuickFix))


TWO_VIOLATIONS = """\
def f():
    a = dict()
    b = list()
    return a, b
"""


class CodeActionTest(LspTest):
    def test_clean_document(self) -> None:
        actions, _ = self.code_actions("x = 1\n", line=0)
        self.assertEqual([], actions)

    def test_range_without_violations(self) -> None:
        actions, _ = self.code_actions(TWO_VIOLATIONS, line=0)
        self.assertEqual([], actions)

    def test_syntax_error(self) -> None:
        # a half-typed document should not raise, it just has nothing to offer
        actions, _ = self.code_actions("def f(:\n", line=0, column=6)
        self.assertEqual([], actions)

    def test_untitled_document(self) -> None:
        # editors open scratch buffers under schemes with no filesystem path
        server = LSP(
            Options(),
            LSPOptions(tcp=None, ws=None, stdio=False, debounce_interval=0),
        )
        server.lsp.protocol._workspace = Workspace(None)
        uri = "untitled:Untitled-1"
        server.lsp.workspace.put_text_document(
            TextDocumentItem(
                uri=uri, language_id="python", version=1, text=TWO_VIOLATIONS
            )
        )
        start = Position(line=1, character=9)
        self.assertIsNone(
            server.code_action(
                CodeActionParams(
                    text_document=TextDocumentIdentifier(uri=uri),
                    range=Range(start=start, end=start),
                    context=CodeActionContext(diagnostics=[]),
                )
            )
        )

    def test_only_filter(self) -> None:
        actions, _ = self.code_actions(
            TWO_VIOLATIONS, line=1, column=9, only=["source.organizeImports"]
        )
        self.assertEqual([], actions)

    def test_offers_fix_and_suppressions(self) -> None:
        actions, _ = self.code_actions(TWO_VIOLATIONS, line=1, column=9)
        self.assertEqual(
            [
                "Fix RewriteToLiteral",
                "Silence RewriteToLiteral with # lint-fixme",
                "Silence RewriteToLiteral with # lint-ignore",
            ],
            [action.title for action in actions],
        )
        for action in actions:
            self.assertEqual(CodeActionKind.QuickFix, action.kind)
            self.assertEqual(
                ["RewriteToLiteral"],
                [found.code for found in action.diagnostics or []],
            )
        self.assertTrue(actions[0].is_preferred)

    def test_fixes_only_the_selected_violation(self) -> None:
        actions, uri = self.code_actions(TWO_VIOLATIONS, line=1, column=9)
        fixed = apply_edits(TWO_VIOLATIONS, self.edits_for(actions[0], uri))
        self.assertEqual(
            "def f():\n    a = {}\n    b = list()\n    return a, b\n", fixed
        )
        # the other violation is untouched, and still reported
        self.assertEqual(["RewriteToLiteral"], self.lint(fixed))

    def test_selection_spanning_both_violations(self) -> None:
        actions, uri = self.code_actions(
            TWO_VIOLATIONS, line=1, column=4, end=Position(2, 14)
        )
        self.assertEqual(6, len(actions))
        fixed = apply_edits(TWO_VIOLATIONS, self.edits_for(actions[3], uri))
        self.assertEqual(
            "def f():\n    a = dict()\n    b = []\n    return a, b\n", fixed
        )

    def test_no_fix_action_without_autofix(self) -> None:
        # `AvoidOrInExcept` reports violations that have no replacement
        source = "try:\n    print()\nexcept ValueError or TypeError:\n    pass\n"
        actions, _ = self.code_actions(source, line=2, column=7)
        self.assertEqual(
            [
                "Silence AvoidOrInExcept with # lint-fixme",
                "Silence AvoidOrInExcept with # lint-ignore",
            ],
            [action.title for action in actions],
        )


SUPPRESSION_CASES = {
    "simple_statement": ("def f():\n    return dict()\n", 1, 11),
    "multiline_call": (
        "import os\n\nvalue = os.path.join(\n    'a',\n    dict(),\n)\n",
        4,
        4,
    ),
    "decorated_function": (
        "import functools\n\n\n@functools.cache\ndef g():\n    return dict()\n",
        5,
        11,
    ),
    "except_handler": (
        "def h():\n    try:\n        pass\n    except Exception:\n        return dict()\n",
        4,
        15,
    ),
    "module_level": ("value = dict()\n", 0, 8),
    "nested_class": (
        "class A:\n    class B:\n        value = dict()\n",
        2,
        16,
    ),
    "inside_if_else": (
        "def f(x):\n    if x:\n        pass\n    else:\n        return dict()\n",
        4,
        15,
    ),
}


class SuppressionTest(LspTest):
    def test_suppression_silences_the_rule(self) -> None:
        for name, (source, line, column) in SUPPRESSION_CASES.items():
            for index, directive in enumerate(("lint-fixme", "lint-ignore")):
                with self.subTest(case=name, directive=directive):
                    self.assertEqual(["RewriteToLiteral"], self.lint(source))
                    actions, uri = self.code_actions(source, line=line, column=column)
                    action = actions[-2 + index]
                    self.assertEqual(
                        f"Silence RewriteToLiteral with # {directive}", action.title
                    )
                    suppressed = apply_edits(source, self.edits_for(action, uri))
                    self.assertIn(f"# {directive}: RewriteToLiteral", suppressed)
                    self.assertEqual([], self.lint(suppressed))

    def test_comment_is_indented_to_match(self) -> None:
        source, line, column = SUPPRESSION_CASES["nested_class"]
        actions, uri = self.code_actions(source, line=line, column=column)
        edits = self.edits_for(actions[-2], uri)
        self.assertEqual("        # lint-fixme: RewriteToLiteral\n", edits[0].new_text)

    def test_matches_document_line_endings(self) -> None:
        source = "def f():\r\n    return dict()\r\n"
        actions, uri = self.code_actions(source, line=1, column=11)
        edits = self.edits_for(actions[-2], uri)
        self.assertEqual("    # lint-fixme: RewriteToLiteral\r\n", edits[0].new_text)
        self.assertEqual([], self.lint(apply_edits(source, edits)))

    def test_suppression_is_a_pure_insertion(self) -> None:
        source, line, column = SUPPRESSION_CASES["simple_statement"]
        actions, uri = self.code_actions(source, line=line, column=column)
        for action in actions[-2:]:
            with self.subTest(title=action.title):
                edit = self.edits_for(action, uri)[0]
                self.assertEqual(edit.range.start, edit.range.end)


class FormatTest(LspTest):
    def test_format_applies_every_fix(self) -> None:
        with self.document(TWO_VIOLATIONS) as (server, uri):
            edits = server.format(
                DocumentFormattingParams(
                    text_document=TextDocumentIdentifier(uri=uri),
                    options=FormattingOptions(tab_size=4, insert_spaces=True),
                )
            )
            assert edits is not None
            self.assertEqual(
                "def f():\n    a = {}\n    b = []\n    return a, b\n",
                apply_edits(TWO_VIOLATIONS, edits),
            )

    def test_format_clean_document(self) -> None:
        with self.document("x = 1\n") as (server, uri):
            edits = server.format(
                DocumentFormattingParams(
                    text_document=TextDocumentIdentifier(uri=uri),
                    options=FormattingOptions(tab_size=4, insert_spaces=True),
                )
            )
            self.assertIn(edits, (None, []))
