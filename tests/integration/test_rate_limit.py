from tests.conftest import needs_services

pytestmark = needs_services


def test_rate_limit_returns_429(make_account, monkeypatch):
    from packages.settings import settings

    a = make_account()
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 5)
    codes = [a.get("/api/v1/tenants/current").status_code for _ in range(8)]
    assert codes[:5] == [200] * 5 and codes[-1] == 429


def test_auth_rate_limit_per_ip(client, monkeypatch):
    from packages.settings import settings
    from packages.storage.redis import get_redis

    for k in get_redis().scan_iter("rl:auth:*"):
        get_redis().delete(k)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MINUTE", 3)
    codes = [client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "Abcdefgh12"}).status_code
             for _ in range(5)]
    assert codes[:3] == [401] * 3 and codes[3:] == [429, 429]
    for k in get_redis().scan_iter("rl:auth:*"):
        get_redis().delete(k)
