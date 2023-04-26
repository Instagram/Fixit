from fixit import LintRule

class NoOpRule(LintRule):
    MESSAGE = "You shouldn't be seeing this"
    VALID = []
    INVALID = []
