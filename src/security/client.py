"""Identificação do cliente em uma API pública e anônima.

- IP (para limitar): vem da conexão ou do X-Forwarded-For, conforme os proxies confiáveis.
  Nunca use um header controlado pelo cliente para limitar, senão basta trocá-lo a cada pedido.
- X-Client-Id (para isolar conversas): um UUID aleatório que o frontend guarda no navegador.
  Funciona como segredo da conversa; não serve como limite.
"""

import hashlib
import ipaddress
import re

from starlette.requests import Request

_CLIENT_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


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


def owner_key(request: Request, ip: str) -> str:
    """Dono das conversas: X-Client-Id válido; sem ele, cai para o IP (compartilhado por NAT)."""
    client_id = request.headers.get("x-client-id", "").strip()
    if _CLIENT_ID.fullmatch(client_id):
        return _digest("client:" + client_id)
    return _digest("ip:" + ip)
