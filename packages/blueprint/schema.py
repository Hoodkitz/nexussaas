"""Blueprint schema validation."""
import json

BLUEPRINT_SCHEMA = {
    "type": "object",
    "required": ["name", "version"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "entities": {"type": "array", "items": {"type": "object"}},
        "endpoints": {"type": "array", "items": {"type": "object"}},
    },
}

def validate_blueprint(blueprint: dict) -> tuple[bool, list[str]]:
    errors = []
    if not isinstance(blueprint, dict):
        return False, ["blueprint must be an object"]
    if "name" not in blueprint:
        errors.append("missing required field: name")
    if "version" not in blueprint:
        errors.append("missing required field: version")
    if "name" in blueprint and not isinstance(blueprint["name"], str):
        errors.append("name must be a string")
    return len(errors) == 0, errors
