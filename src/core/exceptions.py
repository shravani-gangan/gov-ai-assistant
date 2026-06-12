"""Custom exception hierarchy."""


class GovAIBaseError(Exception):
    """Base for all application errors."""


class DocumentParseError(GovAIBaseError):
    """Raised when a GR/PDF cannot be parsed."""


class ComplianceError(GovAIBaseError):
    """Raised when compliance check fails critically."""


class WorkflowError(GovAIBaseError):
    """Raised when the DeerFlow DAG fails to execute."""


class MemoryError(GovAIBaseError):  # noqa: A001
    """Raised on memory read/write failures."""


class ModelInferenceError(GovAIBaseError):
    """Raised when Ollama inference fails after all retries."""