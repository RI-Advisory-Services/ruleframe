class RuleFrameError(Exception):
    """Base exception for ruleframe."""


class BundleValidationError(RuleFrameError):
    """Raised when rule bundle schema is invalid."""


class InputSchemaError(RuleFrameError):
    """Raised when input data cannot satisfy a rule bundle's column requirements."""
