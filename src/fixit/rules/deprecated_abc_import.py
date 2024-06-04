# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Optional, Union

import libcst as cst
from libcst._nodes.expression import Attribute, Name
from libcst._nodes.statement import (
    BaseCompoundStatement,
    ImportAlias,
    ImportFrom,
    SimpleStatementLine,
)

from fixit import Invalid, LintRule, Valid


# The ABCs that have been moved to `collections.abc`
ABCS = frozenset(
    {
        "AsyncGenerator",
        "AsyncIterable",
        "AsyncIterator",
        "Awaitable",
        "Buffer",
        "ByteString",
        "Callable",
        "Collection",
        "Container",
        "Coroutine",
        "Generator",
        "Hashable",
        "ItemsView",
        "Iterable",
        "Iterator",
        "KeysView",
        "Mapping",
        "MappingView",
        "MutableMapping",
        "MutableSequence",
        "MutableSet",
        "Reversible",
        "Sequence",
        "Set",
        "Sized",
        "ValuesView",
    }
)


class DeprecatedABCImport(LintRule):
    """
    Checks for the use of the deprecated collections ABC import. Since python 3.3,
    the Collections Abstract Base Classes (ABC) have been moved to `collections.abc`.
    These ABCs are import errors starting in Python 3.10.
    """

    MESSAGE = "ABCs must be imported from collections.abc"
    PYTHON_VERSION = ">= 3.3"

    VALID = [
        Valid("from collections.abc import Container"),
        Valid("from collections.abc import Container, Hashable"),
        Valid("from collections.abc import (Container, Hashable)"),
        Valid("from collections import defaultdict"),
        Valid("from collections import abc"),
        Valid("import collections"),
        Valid("import collections.abc"),
        Valid("import collections.abc.Container"),
    ]
    INVALID = [
        Invalid(
            "from collections import Container",
            expected_replacement="from collections.abc import Container",
        ),
        Invalid(
            "from collections import Container, Hashable",
            expected_replacement="from collections.abc import Container, Hashable",
        ),
        Invalid(
            "from collections import (Container, Hashable)",
            expected_replacement="from collections.abc import (Container, Hashable)",
        ),
        Invalid(
            "import collections.Container",
            expected_replacement="import collections.abc.Container",
        ),
        Invalid(
            "from collections import defaultdict, Container",
            expected_replacement="from collections import defaultdict\nfrom collections.abc import Container",
        ),
        Invalid(
            "from collections import defaultdict\nfrom collections import Container",
            expected_replacement="from collections import defaultdict\nfrom collections.abc import Container",
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        # If the module needs to updated
        self.update_module = False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        """
        This catches the `from collections import <ABC>` cases
        """
        # Get imports in this statement
        import_names = (
            [name.name.value for name in node.names]
            if type(node.names) is tuple
            else []
        )
        # Filter the imports for ABC imports
        import_names_in_abc = [name in ABCS for name in import_names]
        if (
            node.module
            and node.module.value == "collections"
            and any(import_names_in_abc)
        ):
            # Replacing the case where there are ABCs mixed with non-ABCs requires
            # splitting a single import statement into two separate imports. This
            # cannot be achieved in this method and is offloaded to leaving the module.
            if not all(import_names_in_abc):
                # We set this variable which triggers the `self.report` to be called
                # in `leave_Module`. We report in the `leave_Module`
                # so that we can add an additional `SimpleStatementLine` for the new
                # import
                self.update_module = True
                self.imports_names = import_names
            else:
                self.report(
                    node,
                    replacement=node.with_changes(
                        module=cst.Attribute(
                            value=cst.Name(value="collections"),
                            attr=cst.Name(value="abc"),
                        )
                    ),
                )

    def get_import_from(
        self, node: Union[SimpleStatementLine, BaseCompoundStatement]
    ) -> Optional[ImportFrom]:
        """
        Iterate over a Statement Sequence and return a Statement if it is a
        `cst.ImportFrom` statement.
        """
        if isinstance(node, SimpleStatementLine):
            for statement in node.body:
                # Get the imports in this statement
                import_names = (
                    [
                        name.name.value if isinstance(name, ImportAlias) else None
                        for name in statement.names
                    ]
                    if isinstance(statement, ImportFrom)
                    and isinstance(statement.names, tuple)
                    else []
                )
                if (
                    isinstance(statement, ImportFrom)
                    and statement.module
                    and statement.module.value == "collections"
                    # Ensure the imports in this statement are the ones we are looking for
                    and set(import_names).intersection(set(self.imports_names))
                ):
                    return statement

        return None

    def leave_Module(self, node: cst.Module) -> None:
        """
        While leaving the module, check if we need to split up imports.
        """
        if self.update_module:
            # Filter the ABCs and non-ABCs
            abcs: List[str] = []
            non_abcs: List[str] = []
            for name in self.imports_names:
                (non_abcs, abcs)[name in ABCS].append(name)

            node_body = list(node.body)

            # Iterate over the module to find bad imports
            for idx, statement in enumerate(node_body):
                # Find if the statement is the one we are searching for
                import_statement = self.get_import_from(statement)
                if import_statement:
                    # Remove the original import statement
                    node_body.remove(statement)
                    # Add the non ABC imports
                    node_body.insert(
                        idx,
                        cst.SimpleStatementLine(
                            body=(
                                cst.ImportFrom(
                                    module=cst.Name(value="collections"),
                                    names=[
                                        cst.ImportAlias(name=cst.Name(value=imp))
                                        for imp in non_abcs
                                    ],
                                ),
                            )
                        ),
                    )
                    # Add the ABC imports
                    node_body.insert(
                        idx + 1,
                        cst.SimpleStatementLine(
                            body=(
                                cst.ImportFrom(
                                    module=cst.Attribute(
                                        value=cst.Name(value="collections"),
                                        attr=cst.Name(value="abc"),
                                    ),
                                    names=[
                                        cst.ImportAlias(name=cst.Name(value=imp))
                                        for imp in abcs
                                    ],
                                ),
                            )
                        ),
                    )

            self.report(node, replacement=node.with_changes(body=node_body))

    def visit_ImportAlias(self, node: cst.ImportAlias) -> None:
        """
        This catches the `import collections.<ABC>` cases.
        """
        if (
            type(node.name) is Attribute
            and type(node.name.value) is Name
            and node.name.value.value == "collections"
            and node.name.attr.value in ABCS
        ):
            self.report(
                node,
                replacement=node.with_changes(
                    name=cst.Attribute(
                        value=cst.Attribute(
                            value=cst.Name(value="collections"),
                            attr=cst.Name(value="abc"),
                        ),
                        attr=node.name.attr,
                    )
                ),
            )
