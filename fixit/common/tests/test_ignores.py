# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import tokenize
import unittest
from io import BytesIO
from pathlib import Path
from typing import Container, Iterable, Tuple

import libcst as cst
from parameterized import param, parameterized

from fixit.common.comments import CommentInfo
from fixit.common.ignores import IgnoreInfo
from fixit.common.line_mapping import LineMappingInfo
from fixit.common.report import CstLintRuleReport
from fixit.common.utils import dedent_with_lstrip


class IgnoreInfoTest(unittest.TestCase):
    @parameterized.expand(
        (
            param(
                "noqa_all_legacy",
                **{
                    "source": dedent_with_lstrip(
                        """
                    fn1()
                    fn2()  # noqa
                    fn3()
                    """
                    ),
                    "ignored_code": "IgnoredRule",
                    "ignored_lines": [2],
                },
            ),
            param(
                "noqa_with_code",
                **{
                    "source": dedent_with_lstrip(
                        """
                    fn1()  # noqa: IgnoredRule
                    fn2()  # noqa: IgnoredRule: Message
                    fn3()  # noqa: IgnoredRule, Ignored2Rule: Message
                    fn4()  # noqa: Ignored1Rule
                    fn5()  # noqa: Ignored1Rule, Ignored2Rule
                    fn6()  # noqa: Ignored1Rule, Ignored2Rule: Message
                    """
                    ),
                    "ignored_code": "Ignored1Rule",
                    "ignored_lines": [4, 5, 6],
                },
            ),
            param(
                "noqa_multiline",
                **{
                    "source": dedent_with_lstrip(
                        """
                    fn1(line, \\
                    continuation)  # noqa: IgnoredRule

                    fn2()

                    fn3('''
                        multiline
                        string
                    ''')  # noqa: IgnoredRule
                    """
                    ),
                    "ignored_code": "IgnoredRule",
                    "ignored_lines": [1, 2, 6, 7, 8, 9],
                },
            ),
            param(
                "noqa_file",
                **{
                    "source": dedent_with_lstrip(
                        """
                    # noqa-file: IgnoredRule: Some reason
                    fn1()
                    """
                    ),
                    "ignored_code": "IgnoredRule",
                    "ignored_lines": [1, 2, 3],
                },
            ),
            param(
                "noqa_file_multiple_codes",
                **{
                    "source": dedent_with_lstrip(
                        """
                    # noqa-file: IgnoredRule, Ignored1Rule, Ignored2Rule: Some reason
                    fn1()
                    """
                    ),
                    "ignored_code": "Ignored1Rule",
                    "ignored_lines": [1, 2, 3],
                },
            ),
            param(
                "noqa_file_requires_code_and_reason",
                **{
                    "source": dedent_with_lstrip(
                        """
                    # noqa-file
                    # noqa-file: IgnoredRule
                    # Neither of these noqa-files should work because they're incomplete
                    fn1()
                    """
                    ),
                    "ignored_code": "IgnoredRule",
                    "ignored_lines": [],
                },
            ),
            param(
                "backwards_compatibility_classname",
                **{
                    "source": dedent_with_lstrip(
                        """
                    fn1() # noqa: IG00, IgnoredRule
                    """
                    ),
                    "ignored_code": "IgnoredRule",
                    "ignored_lines": [1],
                },
            ),
            param(
                "backwards_compatibility_oldcode",
                **{
                    "source": dedent_with_lstrip(
                        """
                    fn1() # noqa: IG00, IgnoredRule
                    """
                    ),
                    "ignored_code": "IG00",
                    "ignored_lines": [1],
                },
            ),
            param(
                "lint_fixme",
                **{
                    "source": dedent_with_lstrip(
                        """
                    fn1()

                    # lint-fixme: IgnoredRule: Some short reason
                    fn2(  # this line should be ignored
                        "multiple",  # but these lines shouldn't
                        "arguments",
                    )

                    # lint-fixme: IgnoredRule: Some reason spanning
                    # lint: multiple lines because it's long.
                    fn3('''
                        multiline
                        string
                    ''')  # this function call is a single logical line

                    fn4()
                    """
                    ),
                    "ignored_code": "IgnoredRule",
                    "ignored_lines": [3, 4, 9, 10, 11, 12, 13, 14],
                },
            ),
            param(
                "lint_ignore",
                **{
                    "source": dedent_with_lstrip(
                        """
                    fn1()

                    # lint-ignore: IgnoredRule: Some reason
                    fn2()

                    fn3()
                    """
                    ),
                    "ignored_code": "IgnoredRule",
                    "ignored_lines": [3, 4],
                },
            ),
            param(
                "lint_ignore_eof",
                **{
                    "source": dedent_with_lstrip(
                        """
                    # lint-ignore: IgnoredRule
                    """
                    ),
                    "ignored_code": "IgnoredRule",
                    "ignored_lines": [1, 2],
                },
            ),
        )
    )
    def test_ignored_lines(
        self, _name: str, source: str, ignored_code: str, ignored_lines: Container[int]
    ) -> None:
        tokens = tuple(tokenize.tokenize(BytesIO(source.encode("utf-8")).readline))
        ignore_info = IgnoreInfo.compute(
            comment_info=CommentInfo.compute(tokens=tokens),
            line_mapping_info=LineMappingInfo.compute(tokens=tokens),
            use_noqa=True,
        )
        lines = range(1, tokens[-1].end[0] + 1)
        actual_ignored_lines = []
        for line in lines:
            ignored = ignore_info.should_ignore_report(
                CstLintRuleReport(
                    file_path=Path("fake/path.py"),
                    node=cst.EmptyLine(),
                    code=ignored_code,
                    message="message",
                    line=line,
                    column=0,
                    module=cst.MetadataWrapper(cst.parse_module(source)),
                    module_bytes=source.encode("utf-8"),
                )
            )
            if ignored:
                actual_ignored_lines.append(line)
        # pyre-fixme[6]: Expected `Iterable[Variable[_T]]` for 1st param but got
        #  `Container[int]`.
        self.assertEqual(actual_ignored_lines, list(ignored_lines))

    @parameterized.expand(
        (
            param(
                "unused_noqa",
                **{
                    "source": "fn()  # noqa",
                    "reports_on_lines": [],
                    "unused_comments": [1],
                },
            ),
            param(
                "used_noqa",
                **{
                    "source": "fn()  # noqa",
                    "reports_on_lines": [(1, "Ignored999Rule")],
                    "unused_comments": [],
                },
            ),
            param(
                "unused_lint_ignore",
                **{
                    "source": "# lint-ignore: Ignored999Rule: Some reason\nfn()",
                    "reports_on_lines": [],
                    "unused_comments": [1],
                },
            ),
            param(
                "unused_lint_ignore_mutliple_lines",
                **{
                    "source": "# lint-ignore: Ignored999Rule: Some\n# lint: reason blah blah blah\nfn()",
                    "reports_on_lines": [],
                    "unused_comments": [1],
                },
            ),
            param(
                "used_lint_ignore",
                **{
                    "source": "# lint-ignore: Ignored999Rule: Some reason\nfn()",
                    "reports_on_lines": [(2, "Ignored999Rule")],
                    "unused_comments": [],
                },
            ),
            param(
                "used_lint_ignore_multiple_lines",
                **{
                    "source": "# lint-ignore: Ignored999Rule: Some\n# lint: reason blah blah blah\nfn()",
                    "reports_on_lines": [(3, "Ignored999Rule")],
                    "unused_comments": [],
                },
            ),
            param(
                "lint_ignore_is_used_before_noqa",
                **{
                    "source": "# lint-ignore: Ignored999Rule: Some reason\nfn()  # noqa",
                    "reports_on_lines": [(2, "Ignored999Rule")],
                    "unused_comments": [2],
                },
            ),
            param(
                "duplicate_lint_ignores",
                **{
                    "source": "# lint-ignore: Ignored999Rule: First\n# lint-ignore: Ignored999Rule: Second\nfn()",
                    "reports_on_lines": [(3, "Ignored999Rule")],
                    "unused_comments": [2],
                },
            ),
            param(
                "multiple_used_lint_ignores",
                **{
                    "source": dedent_with_lstrip(
                        """
                    # lint-ignore: Ignored999Rule: Some
                    # lint: reason blah blah blah
                    # lint-ignore: Ignored1000Rule: Some
                    # lint: other reason blah blah
                    fn()
                    """
                    ),
                    "reports_on_lines": [(5, "Ignored999Rule"), (5, "Ignored1000Rule")],
                    "unused_comments": [],
                },
            ),
            param(
                "multiple_unused_lint_ignores",
                **{
                    "source": dedent_with_lstrip(
                        """
                    # lint-ignore: Ignored999Rule: Some
                    # lint: reason blah blah blah
                    # lint-ignore: Ignored1000Rule: Some
                    # lint: other reason blah blah
                    fn()
                    """
                    ),
                    "reports_on_lines": [],
                    "unused_comments": [1, 3],
                },
            ),
            param(
                "some_unused_lint_ignores",
                **{
                    "source": dedent_with_lstrip(
                        """
                    # lint-ignore: Ignored999Rule: Some
                    # lint: reason blah blah blah
                    # lint-ignore: Ignored1000Rule: Some
                    # lint: other reason blah blah
                    fn()
                    """
                    ),
                    "reports_on_lines": [(5, "Ignored999Rule")],
                    "unused_comments": [3],
                },
            ),
            param(
                "some_unused_lint_ignores_2",
                **{
                    "source": dedent_with_lstrip(
                        """
                    # lint-ignore: Ignored999Rule: Some
                    # lint: reason blah blah blah
                    # lint-ignore: Ignored1000Rule: Some
                    # lint: other reason blah blah
                    fn()
                    """
                    ),
                    "reports_on_lines": [(5, "Ignored1000Rule")],
                    "unused_comments": [1],
                },
            ),
        )
    )
    def test_unused_comments(
        self,
        _name: str,
        source: str,
        reports_on_lines: Iterable[Tuple[int, str]],
        unused_comments: Iterable[int],
    ) -> None:
        """
        Verify that we can correctly track which lint comments were used and which were
        unused.

        TODO: We don't track usage of global ignore comments, so we can't know if
        they're unused.
        """
        tokens = tuple(tokenize.tokenize(BytesIO(source.encode("utf-8")).readline))
        ignore_info = IgnoreInfo.compute(
            comment_info=CommentInfo.compute(tokens=tokens),
            line_mapping_info=LineMappingInfo.compute(tokens=tokens),
            use_noqa=True,
        )

        for line, code in reports_on_lines:
            ignore_info.should_ignore_report(
                CstLintRuleReport(
                    file_path=Path("fake/path.py"),
                    node=cst.EmptyLine(),
                    code=code,
                    message="message",
                    line=line,
                    column=0,
                    module=cst.MetadataWrapper(cst.parse_module(source)),
                    module_bytes=source.encode("utf-8"),
                )
            )

        self.assertEqual(
            sorted(
                [
                    min(tok.start[0] for tok in c.tokens)
                    for c in ignore_info.suppression_comments
                    if not c.used_by
                ]
            ),
            sorted(unused_comments),
        )

    def test_multiline_suppression(self) -> None:
        source = """
        # lint-ignore: SomeCode: some reason
        # lint: and some reason continued
        # lint: onto multiple lines.
        x = "Some ignored violation"
        """
        tokens = tuple(tokenize.tokenize(BytesIO(source.encode("utf-8")).readline))
        ignore_info = IgnoreInfo.compute(
            comment_info=CommentInfo.compute(tokens=tokens),
            line_mapping_info=LineMappingInfo.compute(tokens=tokens),
            use_noqa=False,
        )

        self.assertEqual(
            len(ignore_info.local_ignore_info.local_suppression_comments), 1
        )
        local_supp_comment = next(
            lsc for lsc in ignore_info.local_ignore_info.local_suppression_comments
        )
        self.assertEqual(
            local_supp_comment.reason,
            "some reason and some reason continued onto multiple lines.",
        )
        # Verify that all local suppression comment lines map to the same SuppressionComment instance.
        for (
            lines,
            supp_comments,
        ) in ignore_info.local_ignore_info.local_suppression_comments_by_line.items():
            self.assertEqual(len(supp_comments), 1)
            supp_comment = supp_comments[0]
            self.assertIs(supp_comment, local_supp_comment)
