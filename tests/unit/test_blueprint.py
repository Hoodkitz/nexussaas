"""Blueprint module tests."""
from packages.blueprint.validator import validate_blueprint
from packages.blueprint.ddl import generate_ddl
from packages.blueprint.codegen import generate_backend

def test_valid_blueprint():
    bp = {"name": "test", "version": "1.0", "entities": [{"name": "User", "fields": ["id", "email"]}]}
    valid, errors = validate_blueprint(bp)
    assert valid is True
    assert len(errors) == 0

def test_invalid_blueprint():
    bp = {"name": "", "version": "1.0"}
    valid, errors = validate_blueprint(bp)
    assert valid is False
    assert len(errors) > 0

def test_ddl_generation():
    bp = {"entities": [{"name": "User", "fields": ["email"]}]}
    ddl = generate_ddl(bp)
    assert "CREATE TABLE user" in ddl.lower() or "CREATE TABLE User" in ddl

def test_code_generation():
    bp = {"name": "myapp", "version": "1.0"}
    result = generate_backend(bp)
    assert result["status"] == "generated"
    assert "main.py" in str(result["files"])
