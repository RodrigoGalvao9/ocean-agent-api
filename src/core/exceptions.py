class OceanAgentError(Exception):
    """Base exception for application errors."""


class ConfigurationError(OceanAgentError):
    """Raised when required configuration is unavailable."""


class MCPError(OceanAgentError):
    """Raised for MCP connection or invocation errors."""


class GuardrailError(OceanAgentError):
    """Raised when input or tool arguments violate guardrails."""
