from tests.conftest import needs_services


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200 and r.json()["service"] == "NexusSaaS"


def test_healthz_and_request_id(client):
    r = client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assert r.json() == {"status": "ok"} and r.headers["X-Request-ID"] == "abc123"


def test_metrics(client):
    client.get("/healthz")
    r = client.get("/metrics")
    assert r.status_code == 200 and b"nexus_http_requests_total" in r.content


@needs_services
def test_readyz(client):
    assert client.get("/readyz").json()["status"] == "ready"
