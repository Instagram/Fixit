# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from collections import defaultdict
from logging import Handler, Logger, LogRecord, getLogger
from subprocess import TimeoutExpired
from typing import TYPE_CHECKING, DefaultDict, Iterable, List, Mapping, Type

from libcst.metadata import TypeInferenceProvider

from fixit.cli import FullRepoMetadataConfig
from fixit.cli.utils import print_yellow
from fixit.common.base import CstLintRule
from fixit.common.full_repo_metadata import get_repo_caches
from fixit.common.utils import LintRuleCollectionT


if TYPE_CHECKING:
    from libcst.metadata.base_provider import ProviderT


class MetadataCacheErrorHandler(Handler):
    timeout_paths: List[str] = []
    other_exceptions: DefaultDict[Type[Exception], List[str]] = defaultdict(list)

    def emit(self, record: LogRecord) -> None:
        # According to logging documentation, exc_info will be a tuple of three values: (type, value, traceback)
        # see https://docs.python.org/3.8/library/logging.html#logrecord-objects
        exc_info = record.exc_info
        if exc_info is not None:
            exc_type = exc_info[0]
            failed_paths = record.__dict__.get("paths")
            if exc_type is not None:
                # Store exceptions in memory for processing later.
                if exc_type is TimeoutExpired:
                    self.timeout_paths += failed_paths
                else:
                    self.other_exceptions[exc_type] += failed_paths


def rules_require_metadata_cache(rules: LintRuleCollectionT) -> bool:
    return any(
        issubclass(r, CstLintRule) and getattr(r, "requires_metadata_caches")()
        for r in rules
    )


def get_metadata_caches(
    cache_timeout: int, file_paths: Iterable[str]
) -> Mapping[str, Mapping["ProviderT", object]]:
    """
    Returns a metadata cache for each file in ``file_paths``.
    """
    logger: Logger = getLogger("Metadata Caches Logger")
    handler = MetadataCacheErrorHandler()
    logger.addHandler(handler)
    full_repo_metadata_config: FullRepoMetadataConfig = FullRepoMetadataConfig(
        providers={TypeInferenceProvider},
        timeout_seconds=cache_timeout,
        batch_size=100,
        logger=logger,
    )
    metadata_caches = get_repo_caches(file_paths, full_repo_metadata_config)
    # Let user know of any cache retrieval failures.
    if handler.timeout_paths:
        print(
            "Unable to get metadata cache for the following paths:\n"
            + "\n".join(handler.timeout_paths)
        )
        print_yellow("Try increasing the --cache-timeout value or passing fewer files.")
    for k, v in handler.other_exceptions.items():
        print(f"Encountered exception {k} for the following paths:\n" + "\n".join(v))
        print_yellow("Running `pyre start` may solve the issue.")
    return metadata_caches
