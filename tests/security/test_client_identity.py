from starlette.requests import Request

from src.security.client import get_client_ip, owner_key


def _request(headers: dict[str, str], host: str = "10.0.0.1") -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (host, 1234),
    }
    return Request(scope)


def test_uses_connection_ip_without_proxy_trust():
    request = _request({"X-Forwarded-For": "1.2.3.4"}, host="9.9.9.9")
    assert get_client_ip(request, trusted_proxy_hops=0) == "9.9.9.9"


def test_takes_ip_added_by_trusted_proxy_not_the_forged_one():
    # O cliente forjou "6.6.6.6"; o proxy confiável acrescentou o IP real no fim.
    request = _request({"X-Forwarded-For": "6.6.6.6, 203.0.113.7"})
    assert get_client_ip(request, trusted_proxy_hops=1) == "203.0.113.7"


def test_ipv6_is_collapsed_to_its_64_prefix():
    a = get_client_ip(_request({}, host="2001:db8:1:2:aaaa:bbbb:cccc:dddd"), 0)
    b = get_client_ip(_request({}, host="2001:db8:1:2:1111:2222:3333:4444"), 0)
    assert a == b


def test_owner_uses_valid_client_id_otherwise_ip():
    valid = "a" * 32
    with_id = owner_key(_request({"X-Client-Id": valid}), "1.1.1.1")
    other_ip = owner_key(_request({"X-Client-Id": valid}), "2.2.2.2")
    invalid = owner_key(_request({"X-Client-Id": "curto"}), "1.1.1.1")
    no_header = owner_key(_request({}), "1.1.1.1")
    assert with_id == other_ip  # o id vale mais que o IP
    assert invalid == no_header  # id inválido cai para o IP
    assert with_id != no_header
