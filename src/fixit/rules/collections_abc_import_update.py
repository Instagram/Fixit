import libcst as cst
from libcst._nodes.expression import Attribute

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
    TASKS = {"safe"}
    MESSAGE = "Since python 3.3, the Collections Abstract Base Classes (ABC) have been moved to `collections.abc`. This was a deprecation warning up until 3.9, and is an import error in 3.10."
    PYTHON_VERSION = ">= 3.3"

    VALID: list[Valid | str] = [
        Valid("from collections.abc import Container"),
        Valid("from collections.abc import Container, Hashable"),
        Valid("from collections.abc import (Container, Hashable)"),
        Valid("from collections import defaultdict"),
        Valid("from collections import abc"),
        Valid("import collections"),
        Valid("import collections.abc"),
        Valid("import collections.abc.Container"),
    ]
    INVALID: list[Invalid | str] = [
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
        # No expected replacement for this one since it would require updating
        # the parent node in the `visit`. This is due to the need of splitting
        # the import statement into two separate import statements.
        Invalid(
            "from collections import defaultdict, Container",
        ),
    ]

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        import_names = [name.name.value in ABCS for name in node.names]
        if node.module and node.module.value == "collections" and any(import_names):
            # Replacing the case where there are ABCs mixed with non-ABCs requires
            # updating the parent of the `node`. This is due to the need of splitting
            # the import statement into two separate import statements.
            if not all(import_names):
                self.report(node)
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

    def visit_ImportAlias(self, node: cst.ImportAlias) -> None:
        if (
            type(node.name) is Attribute
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
