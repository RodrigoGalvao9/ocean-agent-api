"""Identificação do cliente em uma API pública e anônima.

- IP (para limitar): vem da conexão ou do X-Forwarded-For, conforme os proxies confiáveis.
  Nunca use um header controlado pelo cliente para limitar, senão basta trocá-lo a cada pedido.
- Cookie de sessão (para isolar conversas): emitido e assinado pelo backend.
"""

import hashlib
import hmac
import ipaddress
import re
import secrets

from starlette.requests import Request

SESSION_COOKIE = "ocean_session"
_SESSION_TOKEN = re.compile(r"^[a-f0-9]{64}\.[a-f0-9]{64}$")
_DEVELOPMENT_SESSION_SECRET = secrets.token_hex(32)


def _normalize_ip(raw: str) -> str:
    try:
        ip = ipaddress.ip_address(raw.strip())
    except ValueError:
        return "unknown"
    if isinstance(ip, ipaddress.IPv6Address):
        # Um /64 é o que um usuário doméstico controla; evita burlar o limite trocando de IPv6.
        return str(ipaddress.ip_network(f"{ip}/64", strict=False).network_address) + "/64"
    return str(ip)


def get_client_ip(request: Request, trusted_proxy_hops: int) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if trusted_proxy_hops > 0 and forwarded:
        parts = [p for p in (item.strip() for item in forwarded.split(",")) if p]
        if len(parts) >= trusted_proxy_hops:
            # O proxy confiável acrescenta o IP real do cliente ao FIM da lista;
            # o que vem antes pode ter sido forjado pelo cliente.
            return _normalize_ip(parts[-trusted_proxy_hops])
    host = request.client.host if request.client else ""
    return _normalize_ip(host)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def ip_key(ip: str) -> str:
    return _digest("ip:" + ip)


def _session_secret(configured_secret: str) -> str:
    return configured_secret or _DEVELOPMENT_SESSION_SECRET


def _sign_session(identifier: str, secret: str) -> str:
    signature = hmac.new(
        _session_secret(secret).encode("utf-8"),
        identifier.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{identifier}.{signature}"


def _new_session(secret: str) -> str:
    identifier = secrets.token_hex(32)
    return _sign_session(identifier, secret)


def _valid_session(value: str, secret: str) -> bool:
    if not _SESSION_TOKEN.fullmatch(value):
        return False
    identifier, signature = value.split(".", 1)
    expected = _sign_session(identifier, secret).split(".", 1)[1]
    return hmac.compare_digest(signature, expected)


def establish_session(request: Request, secret: str) -> tuple[str, bool]:
    """Obtém uma sessão assinada pelo backend ou cria uma para a resposta atual."""
    current = request.cookies.get(SESSION_COOKIE, "")
    if _valid_session(current, secret):
        request.state.conversation_session = current
        request.state.new_conversation_session = False
        return current, False

    created = _new_session(secret)
    request.state.conversation_session = created
    request.state.new_conversation_session = True
    return created, True


def owner_key(request: Request, ip: str, session_secret: str = "") -> str:
    """Dono das conversas: sessão assinada pelo backend, nunca um header do cliente."""
    session = getattr(request.state, "conversation_session", None)
    if not session:
        session, _ = establish_session(request, session_secret)
    return _digest("session:" + session)
