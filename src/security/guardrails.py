import re
from collections.abc import Mapping

from src.core.exceptions import GuardrailError

MAX_MESSAGE_LENGTH = 4000
BLOCKED_PATTERNS = (
    re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions|prompts)"),
    re.compile(r"(?i)reveal\s+(?:the\s+)?(?:system\s+prompt|api\s*key|secret|credential)"),
)


def validate_user_message(message: str) -> str:
    if not isinstance(message, str) or not message.strip():
        raise GuardrailError("message must not be empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise GuardrailError("message exceeds the maximum allowed length")
    if any(pattern.search(message) for pattern in BLOCKED_PATTERNS):
        raise GuardrailError("message contains unsafe instructions")
    return message.strip()


def validate_tool_invocation(name: str, arguments: Mapping[str, object]) -> None:
    if not name or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", name):
        raise GuardrailError("invalid MCP tool name")
    if not isinstance(arguments, Mapping):
        raise GuardrailError("invalid MCP tool arguments")
