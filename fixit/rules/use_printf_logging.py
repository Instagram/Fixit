# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Set, Union

import libcst as cst
import libcst.matchers as m
from fixit import CstContext, CstLintRule
from fixit import InvalidTestCase as Invalid
from fixit import ValidTestCase as Valid

LOG_FUNCTIONS: List[str] = [
    "critical",
    "exception",
    "error",
    "warning",
    "info",
    "debug",
    "log",
]


def check_getLogger(node: Union[cst.Assign, cst.AnnAssign]) -> bool:
    # Check that logging.getLogger() is being assigned
    assign_val = node.value
    if assign_val is None:
        return False
    return m.matches(
        assign_val,
        m.Call(
            func=m.Attribute(
                value=m.Name(value="logging"), attr=m.Name(value="getLogger")
            )
        ),
    )


def match_logger_calls(node: cst.Call, loggers: Set[str]) -> bool:
    # Check if there is a log call to a logger
    return m.matches(
        node,
        m.Call(
            func=m.Attribute(
                value=m.Name(value=m.MatchIfTrue(lambda n: n in loggers)),
                attr=m.Name(value=m.MatchIfTrue(lambda n: n in LOG_FUNCTIONS)),
            )
        ),
    )


def match_calls_str_format(node: cst.Call) -> bool:
    # Check if a call to str.format() is being made
    return m.matches(
        node,
        m.Call(
            func=m.Attribute(
                value=m.OneOf(m.SimpleString(), m.ConcatenatedString()),
                attr=m.Name("format"),
            )
        ),
    )


class UsePrintfLoggingRule(CstLintRule):
    MESSAGE: str = (
        "UsePrintfLoggingRule: Use %s style strings instead of f-string or format() "
        + "for python logging. Pass %s values as arguments or in the 'extra' argument "
        + "in loggers."
    )

    VALID = [
        # Printf strings in log statements are best practice
        Valid('logging.error("Hello %s", my_val)'),
        Valid('logging.info("Hello %(my_str)s!", {"my_str": "world"})'),
        Valid(
            """
            logger = logging.getLogger()
            logger.log(logging.DEBUG, "Concat " "Printf string %s", vals)
            logger.debug("Hello %(my_str)s!", {"my_str": "world"})
            """,
        ),
        Valid(
            """
            mylog = logging.getLogger()
            mylog.warning("A printf string %s, %d", 'George', 732)
            """,
        ),
        # Don't report if logger isn't a logging.getLogger
        Valid('logger.error("Hello %s", my_val)'),
        Valid(
            """
            logger = custom_logger.getLogger()
            logger.error("Hello %s", my_val)
            """,
        ),
        # fstrings should be allowed elsewhere
        Valid(
            """
            logging.warning("simple error %s", test)
            fn(f"formatted string {my_var}")
            """,
        ),
        Valid(
            """
            logger: logging.Logger = logging.getLogger()
            logger.warning("simple error %s", test)
            test_var = f"test string {msg}"
            func(3, other_var, "string format {}".format(test_var))
            """,
        ),
        # %s interpolation allowed outside of log calls
        Valid('test = "my %s" % var'),
    ]

    INVALID = [
        # Using fstring in a log
        Invalid('logging.error(f"Hello {my_var}")'),
        Invalid(
            """
            logger = logging.getLogger()
            logger.error("Cat" f"Hello {my_var}")
            """,
        ),
        # Using str.format() in a log
        Invalid('logging.info("Hello {}".format(my_str))'),
        # Also invalid to use either in loggers
        Invalid(
            """
            logger: logging.Logger = logging.getLogger()
            logger.log("DEBUG", f"Format string {vals}")
            """,
        ),
        Invalid(
            """
            log = logging.getLogger()
            log.warning("This string formats {}".format(foo))
            """,
        ),
        # Do not interpolate %s strings in log
        Invalid('logging.error("my error: %s" % msg)'),
    ]

    def __init__(self, context: CstContext) -> None:
        super().__init__(context)
        self.logging_stack: Set[cst.Call] = set()
        self.logger_names: Set[str] = {"logging"}

    def visit_Assign(self, node: cst.Assign) -> None:
        # Store the assignment of logger = logging.getLogger()
        if check_getLogger(node):
            target = node.targets[0].target
            if m.matches(target, m.Name()):
                self.logger_names.add(cst.ensure_type(target, cst.Name).value)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        # Store the assignment of logger: logging.Logger = logging.getLogger()
        if check_getLogger(node):
            if m.matches(node.target, m.Name()):
                self.logger_names.add(cst.ensure_type(node.target, cst.Name).value)

    def visit_Call(self, node: cst.Call) -> None:
        # Record if we are in a call to a log function
        if match_logger_calls(node, self.logger_names):
            self.logging_stack.add(node)

        # Check and report calls to str.format() in calls to log functions
        if self.logging_stack and match_calls_str_format(node):
            self.report(node)

    def leave_Call(self, original_node: cst.Call) -> None:
        # Record leaving a call to a log function
        if original_node in self.logging_stack:
            self.logging_stack.remove(original_node)

    def visit_FormattedString(self, node: cst.FormattedString) -> None:
        # Report if using a formatted string inside a logging call
        if self.logging_stack:
            self.report(node)

    def visit_BinaryOperation(self, node: cst.BinaryOperation) -> None:
        if not self.logging_stack:
            return
        if m.matches(
            node,
            m.BinaryOperation(
                left=m.OneOf(m.SimpleString(), m.ConcatenatedString()),
                operator=m.Modulo(),
            ),
        ):
            self.report(node)
