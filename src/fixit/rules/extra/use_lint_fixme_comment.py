# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import libcst as cst

from fixit import Invalid, LintRule, Valid


class UseLintFixmeComment(LintRule):
    """
    To silence a lint warning, use ``lint-fixme`` (when plans to fix the issue later) or ``lint-ignore``
    (when the lint warning is not valid) comments.
    The comment requires to be in a standalone comment line and follows the format ``lint-fixme: RULE_NAMES EXTRA_COMMENTS``.
    It suppresses the lint warning with the RULE_NAMES in the next line.
    RULE_NAMES can be one or more lint rule names separated by comma.
    ``noqa`` is deprecated and not supported because explicitly providing lint rule names to be suppressed
    in lint-fixme comment is preferred over implicit noqa comments. Implicit noqa suppression comments
    sometimes accidentally silence warnings unexpectedly.
    """

    MESSAGE: str = "noqa is deprecated. Use `lint-fixme` or `lint-ignore` instead."

    VALID = [
        Valid(
            """
            # lint-fixme: UseFstringRule
            "%s" % "hi"
            """
        ),
        Valid(
            """
            # lint-ignore: UsePlusForStringConcatRule
            'ab' 'cd'
            """
        ),
    ]
    INVALID = [
        Invalid("fn() # noqa"),
        Invalid(
            """
            (
             1,
             2,  # noqa
            )
            """
        ),
        Invalid(
            """
            class C:
                # noqa
                ...
            """
        ),
    ]

    def visit_Comment(self, node: cst.Comment) -> None:
        target = "# noqa"
        if node.value[: len(target)].lower() == target:
            self.report(node)
