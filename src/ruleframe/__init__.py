"""Public API for RuleFrame."""

from importlib.metadata import version

from .bundle import RuleBundle
from .exceptions import BundleValidationError, InputSchemaError, RuleFrameError
from .result import ValidationResult
from .validation import validate_dataframe

__version__ = version("ruleframe")

__all__ = [
    "BundleValidationError",
    "InputSchemaError",
    "RuleBundle",
    "RuleFrameError",
    "ValidationResult",
    "__version__",
    "validate_dataframe",
]
