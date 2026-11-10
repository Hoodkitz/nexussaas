from tests.conftest import needs_services

pytestmark = needs_services


def test_requires_login(client):
    assert client.get("/api/v1/blueprint/next-question").status_code == 401
    assert client.post("/api/v1/blueprint/draft", json={"answers": {"a": "b"}}).status_code == 401


def test_draft_falls_back_without_llm(make_account, monkeypatch):
    from apps.api.routers import blueprint

    async def none(*a, **k):
        return None

    monkeypatch.setattr(blueprint, "complete_json", none)
    a = make_account()
    r = a.post("/api/v1/blueprint/draft", json={"answers": {"app_description": "Dienstplan für die Feuerwehr"}})
    assert r.status_code == 200 and r.json()["source"] == "fallback"
    assert a.post("/api/v1/jobs", json={"blueprint": r.json()["blueprint"]}).status_code == 201


def test_invalid_llm_draft_is_replaced(make_account, monkeypatch):
    from apps.api.routers import blueprint

    async def bad(*a, **k):
        return {"name": "x", "entities": [{"name": "class", "fields": [{"name": "a", "type": "exec"}]}]}

    monkeypatch.setattr(blueprint, "complete_json", bad)
    a = make_account()
    r = a.post("/api/v1/blueprint/draft", json={"answers": {"app_description": "Test"}})
    assert r.json()["source"] == "fallback"


def test_research_sanitizes_questions(make_account, monkeypatch):
    from apps.api.routers import blueprint

    async def q(*a, **k):
        return {"research": "x" * 5000, "follow_up_questions": [{"id": "Drop Table!", "q": "Wie viele <b>Nutzer</b>"}] * 9}

    monkeypatch.setattr(blueprint, "complete_json", q)
    a = make_account()
    d = a.post("/api/v1/blueprint/research", json={"question_id": "x", "answer": "y"}).json()
    assert len(d["research"]) <= 600 and len(d["follow_up_questions"]) == 4
    assert d["follow_up_questions"][0]["id"] == "drop_table" and d["follow_up_questions"][0]["q"].endswith("?")
