"""Blueprint validation tests."""
from packages.blueprint.schema import validate_blueprint

def test_valid_blueprint():
    bp = {"name": "test-app", "version": "1.0", "description": "A test"}
    ok, errors = validate_blueprint(bp)
    assert ok
    assert errors == []

def test_missing_name():
    bp = {"version": "1.0"}
    ok, errors = validate_blueprint(bp)
    assert not ok
    assert any("name" in e for e in errors)

def test_missing_version():
    bp = {"name": "test-app"}
    ok, errors = validate_blueprint(bp)
    assert not ok
    assert any("version" in e for e in errors)

def test_not_dict():
    ok, errors = validate_blueprint("string")
    assert not ok
