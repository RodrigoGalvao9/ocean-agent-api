from starlette.requests import Request

from src.security.client import SESSION_COOKIE, establish_session, get_client_ip, owner_key


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


def test_owner_uses_backend_signed_session_not_client_header():
    secret = "s" * 64
    issuing_request = _request({})
    session, created = establish_session(issuing_request, secret)
    assert created

    with_session = owner_key(
        _request({"Cookie": f"{SESSION_COOKIE}={session}", "X-Client-Id": "a" * 32}),
        "1.1.1.1",
        secret,
    )
    same_session = owner_key(
        _request({"Cookie": f"{SESSION_COOKIE}={session}", "X-Client-Id": "b" * 32}),
        "2.2.2.2",
        secret,
    )
    forged_value = session[:-1] + ("0" if session[-1] != "0" else "1")
    forged_session = owner_key(
        _request({"Cookie": f"{SESSION_COOKIE}={forged_value}"}),
        "1.1.1.1",
        secret,
    )

    assert with_session == same_session
    assert with_session != forged_session
