"""Guardrails de entrada: mensagem do usuário e chamadas de ferramenta.

O filtro de mensagens é uma lombada, não uma muralha: pega as tentativas óbvias (em português e
em inglês) e ignora truques triviais de escrita (acento, caixa, caracteres invisíveis). A defesa
de verdade são a allowlist de ferramentas, o prompt restritivo e o fato de as ferramentas serem
somente leitura.
"""

import math
import re
import unicodedata
from collections.abc import Mapping

from src.core.exceptions import GuardrailError

MAX_MESSAGE_LENGTH = 4000

MAX_TOOL_ARGUMENTS = 10
MAX_TOOL_STRING_LENGTH = 1000
MAX_TOOL_LIST_ITEMS = 20
MAX_TOOL_NUMBER = 1e9

_TOOL_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_ARGUMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _fold(text: str) -> str:
    """Texto comparável: sem acento, minúsculo, sem caracteres invisíveis, espaços únicos."""
    decomposed = unicodedata.normalize("NFKD", text)
    kept = []
    for char in decomposed:
        category = unicodedata.category(char)
        if category in ("Mn", "Cf"):  # acento combinado, zero-width, marcas de direção
            continue
        kept.append(" " if category.startswith("C") or char.isspace() else char)
    return re.sub(r"\s+", " ", "".join(kept)).strip().lower()


_IGNORE_VERB = r"(?:ignor|desconsider|esquec|descart|desobedec|despreze|contorn|burl|sobrescrev)\w*"
_RULE_NOUN = r"(?:instruc|regra|ordem|ordens|diretriz|orientac|restric|prompt|comando)\w*"
_REVEAL_VERB = (
    r"(?:revel|mostr|exib|imprim|repit|dit[ea]|diga|passe|envi|vaz|copi|cole|list|"
    r"reveal|show|print|repeat|display|leak|dump|output|tell|give|what\s+is|qual\s+(?:e|eh))\w*"
)

BLOCKED_PATTERNS = tuple(
    re.compile(p)
    for p in (
        # "ignore as instruções anteriores", "desconsidere as regras do sistema"
        rf"\b{_IGNORE_VERB}\s+(?:\w+\s+){{0,3}}{_RULE_NOUN}\s+(?:\w+\s+){{0,2}}"
        r"(?:anterior\w*|previa\w*|acima|do sistema|de sistema|iniciais?|originais?|internas?)",
        # "ignore suas instruções", "esqueça todas as suas regras"
        rf"\b{_IGNORE_VERB}\s+(?:\w+\s+){{0,2}}(?:suas|seus|tuas|teus)\s+(?:\w+\s+)?{_RULE_NOUN}",
        # "ignore all previous instructions", "forget your rules"
        r"\b(?:ignore|disregard|forget|override|bypass)\s+(?:\w+\s+){0,3}"
        r"(?:previous|prior|above|earlier|system|initial|original|your)\s+(?:\w+\s+)?"
        r"(?:instructions|rules|prompts?|guidelines|directions)",
        # prompt/instruções internas, mesmo sem verbo ("qual o seu system prompt?")
        r"\b(?:system prompt|prompt (?:do|de) sistema|prompt interno|prompt inicial|"
        r"instrucoes (?:internas|do sistema|de sistema|iniciais|ocultas)|"
        r"hidden instructions|developer message)\b",
        rf"\b{_REVEAL_VERB}\s+(?:\w+\s+){{0,4}}(?:suas|seu|your)\s+(?:instrucoes|prompt|instructions)",
        # chaves e credenciais
        r"\b(?:api ?key|chaves? (?:de|da|do) ?(?:api|acesso|sistema|servidor|groq|openrouter)|"
        r"chave secreta|secret key|session secret)\b",
        r"\b(?:groq_api_key|openrouter_api_key|mcp_auth_token|conversation_session_secret|"
        r"database_url|langfuse_secret_key|metrics_token)\b",
        rf"\b{_REVEAL_VERB}\s+(?:\w+\s+){{0,4}}"
        r"(?:senhas?|segredos?|credenciais|credencial|token (?:de acesso|do mcp|secreto|bearer)|"
        r"passwords?|credentials?|secrets?|variaveis? de ambiente|environment variables?)\b",
        # jailbreak declarado
        r"\b(?:modo desenvolvedor|developer mode|jailbreak|modo deus|god mode|do anything now)\b",
        r"\b(?:desativ|remov|desligu|contorn|burl)\w*\s+(?:\w+\s+){0,2}"
        r"(?:guardrails?|filtros? de seguranca|protecoes? de seguranca|restricoes? de seguranca)",
        # marcadores de papel de templates de chat colados no texto
        r"<\|?(?:im_start|im_end|system|assistant|user)\|?>|\[/?inst\]|<</?sys>>",
    )
)


def is_blocked(message: str) -> bool:
    """True se a mensagem tenta sobrescrever instruções ou extrair prompt e credenciais."""
    if not isinstance(message, str):
        return False
    folded = _fold(message)
    return any(pattern.search(folded) for pattern in BLOCKED_PATTERNS)


def validate_user_message(message: str) -> str:
    if not isinstance(message, str) or not message.strip():
        raise GuardrailError("message must not be empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise GuardrailError("message exceeds the maximum allowed length")
    if is_blocked(message):
        raise GuardrailError("message contains unsafe instructions")
    return message.strip()


def _check_scalar(value: object) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise GuardrailError("invalid MCP tool arguments")
        if abs(value) > MAX_TOOL_NUMBER:
            raise GuardrailError("invalid MCP tool arguments")
        return
    if isinstance(value, str):
        if len(value) > MAX_TOOL_STRING_LENGTH or _CONTROL_CHARS.search(value):
            raise GuardrailError("invalid MCP tool arguments")
        return
    raise GuardrailError("invalid MCP tool arguments")


def validate_tool_invocation(
    name: str,
    arguments: Mapping[str, object],
    *,
    allowed_tools: frozenset[str] | set[str] | None = None,
    allowed_arguments: frozenset[str] | set[str] | None = None,
) -> None:
    """Última barreira antes de chamar o MCP.

    `allowed_tools` e `allowed_arguments` (nomes que o esquema da ferramenta declara) são
    opcionais; quando informados, nome ou argumento desconhecido é recusado.
    """
    if not name or not _TOOL_NAME.fullmatch(name):
        raise GuardrailError("invalid MCP tool name")
    if allowed_tools is not None and name not in allowed_tools:
        raise GuardrailError("MCP tool is not allowed")
    if not isinstance(arguments, Mapping):
        raise GuardrailError("invalid MCP tool arguments")
    if len(arguments) > MAX_TOOL_ARGUMENTS:
        raise GuardrailError("too many MCP tool arguments")
    for key, value in arguments.items():
        if not isinstance(key, str) or not _ARGUMENT_NAME.fullmatch(key):
            raise GuardrailError("invalid MCP tool argument name")
        if allowed_arguments is not None and key not in allowed_arguments:
            raise GuardrailError("unexpected MCP tool argument")
        if isinstance(value, (list, tuple)):
            if len(value) > MAX_TOOL_LIST_ITEMS:
                raise GuardrailError("invalid MCP tool arguments")
            for item in value:
                _check_scalar(item)
        else:
            _check_scalar(value)
