class RuleFrameError(Exception):
    """Base exception for ruleframe."""


class BundleValidationError(RuleFrameError):
    """Raised when rule bundle schema is invalid."""
