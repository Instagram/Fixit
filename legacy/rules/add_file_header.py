# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List

import libcst as cst
import libcst.matchers as m

from fixit import (
    CstContext,
    CstLintRule,
    InvalidTestCase as Invalid,
    LintConfig,
    ValidTestCase as Valid,
)


class AddMissingHeaderRule(CstLintRule):
    """
    Verify if required header comments exist in a module.
    Configuration is required in ``.fixit.config.yaml`` in order to enable this rule::

        rule_config:
           AddMissingHeaderRule:
               path: pkg/*.py
               header: |-
                   # header line 1
                   # header line 2

    (Use ``|-`` to keep newlines and add no new line at the end of header comments.)
    ``path`` is a glob-style ``str`` used in `Path.match() <https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.match>`_.
    The specified ``header`` is a newline-separated ``str`` to be enforced in files whose path matches.
    """

    MESSAGE: str = "A required header comment for this file is missing."

    VALID = [
        Valid("import libcst"),
        Valid(
            """
            # header line 1
            # header line 2
            import libcst
            """,
            config=LintConfig(
                rule_config={
                    "AddMissingHeaderRule": {
                        "path": "*.py",
                        "header": "# header line 1\n# header line 2",
                    }
                }
            ),
        ),
        Valid(
            """
            # header line 1
            # header line 2
            # An extra header line is ok
            import libcst
            """,
            config=LintConfig(
                rule_config={
                    "AddMissingHeaderRule": {
                        "path": "*.py",
                        "header": "# header line 1\n# header line 2",
                    }
                }
            ),
        ),
        Valid(
            """
            # other header in an unrelated file
            import libcst
            """,
            filename="b/m.py",
            config=LintConfig(
                rule_config={
                    "AddMissingHeaderRule": {
                        "path": "a/*.py",
                        "header": "# header line 1\n# header line 2",
                    }
                }
            ),
        ),
    ]
    INVALID = [
        Invalid(
            "# wrong header",
            config=LintConfig(
                rule_config={
                    "AddMissingHeaderRule": {"path": "*.py", "header": "# header line"}
                }
            ),
            expected_replacement="# header line\n# wrong header",
        ),
        Invalid(
            """
            #!/usr/bin/env python
            # wrong header""",
            config=LintConfig(
                rule_config={
                    "AddMissingHeaderRule": {"path": "*.py", "header": "# header line"}
                }
            ),
            expected_replacement="#!/usr/bin/env python\n# header line\n# wrong header",
        ),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        config = self.context.config.rule_config.get(self.__class__.__name__, None)
        if config is None:
            self.rule_disabled: bool = True
        else:
            if not isinstance(config, dict) or "header" not in config:
                raise ValueError(
                    "A ``header`` str config is required by AddMissingHeaderRule."
                )
            header_str = config["header"]
            if not isinstance(header_str, str):
                raise ValueError(
                    "A ``header`` str config is required by AddMissingHeaderRule."
                )
            lines = header_str.split("\n")
            self.header_matcher: List[m.EmptyLine] = [
                m.EmptyLine(comment=m.Comment(value=line)) for line in lines
            ]
            self.header_replacement: List[cst.EmptyLine] = [
                cst.EmptyLine(comment=cst.Comment(value=line)) for line in lines
            ]
            if "path" in config:
                path_pattern = config["path"]
                if not isinstance(path_pattern, str):
                    raise ValueError(
                        "``path`` config should be a str in AddMissingHeaderRule."
                    )
            else:
                path_pattern = "*.py"
            self.rule_disabled = not self.context.file_path.match(path_pattern)

    def visit_Module(self, node: cst.Module) -> None:
        if self.rule_disabled:
            return
        if not m.matches(node, m.Module(header=[*self.header_matcher, m.ZeroOrMore()])):
            shebang, header = [], node.header
            if header:
                comment = header[0].comment
                if isinstance(comment, cst.Comment) and comment.value.startswith("#!"):
                    shebang, header = [header[0]], header[1:]
            self.report(
                node,
                replacement=node.with_changes(
                    header=[*shebang, *self.header_replacement, *header]
                ),
            )
