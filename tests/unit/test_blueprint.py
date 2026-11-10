"""Blueprint normalization, DDL and code generation (no services needed)."""
import json
from pathlib import Path

import pytest

from packages.blueprint.codegen import generate_backend
from packages.blueprint.ddl import generate_ddl
from packages.blueprint.package import build_zip
from packages.blueprint.schema import BlueprintError, normalize_blueprint, validate_blueprint
from packages.security.scanner import security_review, static_checks

SAMPLE = json.loads((Path(__file__).parent.parent / "fixtures" / "sample_blueprint.json").read_text())


def test_sample_normalizes():
    bp = normalize_blueprint(SAMPLE)
    assert bp["name"] == "sample_app"
    assert [e["table"] for e in bp["entities"]] == ["users", "projects"]
    assert {f["name"] for f in bp["entities"][0]["fields"]} == {"email", "name"}  # id is implicit


@pytest.mark.parametrize("bad", [
    {"entities": [{"name": "x"}]},
    {"name": "ok", "entities": []},
    {"name": "ok", "entities": [{"name": "class"}]},
    {"name": "ok", "entities": [{"name": "a; DROP TABLE x"}]},
    {"name": "ok", "entities": [{"name": "a", "fields": [{"name": "b", "type": "blob"}]}]},
    {"name": "ok", "entities": [{"name": "a", "fields": [{"name": "b", "type": "ref:missing"}]}]},
    {"name": "ok", "entities": [{"name": "item"}, {"name": "items"}]},
    {"name": "ok", "entities": [{"name": "a", "fields": [{"name": "model_dump"}]}]},
    "not an object",
])
def test_invalid_blueprints(bad):
    ok, errors = validate_blueprint(bad)
    assert not ok and errors
    with pytest.raises(BlueprintError):
        normalize_blueprint(bad)


def test_ddl_has_rls_and_types():
    bp = normalize_blueprint({"name": "a", "entities": [
        {"name": "Task", "fields": [{"name": "title", "type": "text", "required": True, "max_length": 80},
                                    {"name": "owner", "type": "ref:Task"}, {"name": "n", "type": "int"}]}]})
    ddl = generate_ddl(bp)
    assert '"title" VARCHAR(80) NOT NULL' in ddl and '"n" INTEGER' in ddl
    assert 'ALTER TABLE "tasks" FORCE ROW LEVEL SECURITY' in ddl
    assert "REFERENCES \"tasks\" (id)" in ddl


def test_generation_is_deterministic():
    bp = normalize_blueprint(SAMPLE)
    a, b = generate_backend(bp), generate_backend(normalize_blueprint(SAMPLE))
    assert a == b
    assert build_zip(a, "x")[1] == build_zip(b, "x")[1]


def test_generated_code_passes_static_and_security_checks():
    bp = normalize_blueprint({"name": "shop", "description": "'''; import os; os.system('x') #", "entities": [
        {"name": "Product", "fields": [{"name": "title", "type": "text", "required": True},
                                       {"name": "price", "type": "float"}, {"name": "tags", "type": "json"},
                                       {"name": "sku", "type": "text", "unique": True}]},
        {"name": "Order", "fields": [{"name": "product_id", "type": "ref:Product"},
                                     {"name": "email", "type": "email", "required": True},
                                     {"name": "placed", "type": "timestamp"}, {"name": "day", "type": "date"}]}]})
    files = generate_backend(bp)
    assert static_checks(files)["passed"], static_checks(files)["findings"]
    assert security_review(files, ["products", "orders"])["passed"]
    # free text is escaped, not executed
    assert "description=\"'''; import os" in files["app/main.py"] or "\\'" in files["app/main.py"]


def test_secret_scan_catches_secrets():
    files = {"app/x.py": 'API_KEY = "sk_live_0123456789abcdefABCD"\n'}
    assert not security_review(files, [])["passed"]
