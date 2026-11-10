"""Blueprint validation and normalization.

Accepts the user-facing blueprint (loose) and returns a canonical, fully validated
form that the generators consume. All identifiers that end up in SQL or Python are
validated against a strict allowlist, so generators never interpolate raw input.
"""
from __future__ import annotations

import keyword
import re
from typing import Any

IDENT_RE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
FIELD_TYPES = {"text", "integer", "float", "boolean", "timestamp", "date", "uuid", "jsonb", "email"}
TYPE_ALIASES = {"string": "text", "str": "text", "int": "integer", "number": "float", "bool": "boolean",
                "datetime": "timestamp", "json": "jsonb"}
RESERVED_FIELDS = {"id", "tenant_id", "created_at", "updated_at"}
RESERVED_PY = {"model_config", "model_fields", "schema", "json", "dict", "copy", "validate", "metadata",
               "registry", "query"}
MAX_ENTITIES = 30
MAX_FIELDS = 50
MAX_TEXT = 2000


class BlueprintError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def snake(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z]+", "_", name.strip())
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s).lower().strip("_")
    s = re.sub(r"_+", "_", s)
    return s


def pascal(ident: str) -> str:
    return "".join(p.capitalize() for p in ident.split("_"))


def _ident(raw: Any, what: str, errors: list[str]) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        errors.append(f"{what}: Name fehlt")
        return None
    ident = snake(raw)
    if not IDENT_RE.match(ident) or keyword.iskeyword(ident) or ident in RESERVED_PY or ident.startswith("model_"):
        errors.append(f"{what}: ungültiger Name {raw!r}")
        return None
    return ident


def _text(raw: Any, limit: int = MAX_TEXT) -> str:
    return raw.strip()[:limit] if isinstance(raw, str) else ""


def normalize_blueprint(bp: Any) -> dict:
    """Validate and normalize. Raises BlueprintError with all problems found."""
    errors: list[str] = []
    if not isinstance(bp, dict):
        raise BlueprintError(["Blueprint muss ein Objekt sein"])
    name = _ident(bp.get("name"), "App", errors)
    version = bp.get("version", "1.0")
    if not isinstance(version, str) or not re.match(r"^[0-9A-Za-z.\-]{1,20}$", version):
        errors.append("version ungültig")
        version = "1.0"

    raw_entities = bp.get("entities") or []
    if not isinstance(raw_entities, list):
        errors.append("entities muss eine Liste sein")
        raw_entities = []
    if not raw_entities:
        errors.append("Mindestens eine Entität ist nötig")
    if len(raw_entities) > MAX_ENTITIES:
        errors.append(f"Maximal {MAX_ENTITIES} Entitäten")
        raw_entities = raw_entities[:MAX_ENTITIES]

    entities: list[dict] = []
    seen_entities: set[str] = set()
    for i, raw in enumerate(raw_entities):
        if isinstance(raw, str):
            raw = {"name": raw, "fields": []}
        if not isinstance(raw, dict):
            errors.append(f"Entität {i}: muss ein Objekt sein")
            continue
        ename = _ident(raw.get("name"), f"Entität {i}", errors)
        if not ename:
            continue
        if ename in seen_entities:
            errors.append(f"Entität {ename}: doppelt")
            continue
        seen_entities.add(ename)
        fields: list[dict] = []
        seen_fields: set[str] = set()
        raw_fields = raw.get("fields") or []
        if not isinstance(raw_fields, list):
            errors.append(f"{ename}: fields muss eine Liste sein")
            raw_fields = []
        if len(raw_fields) > MAX_FIELDS:
            errors.append(f"{ename}: maximal {MAX_FIELDS} Felder")
            raw_fields = raw_fields[:MAX_FIELDS]
        for j, f in enumerate(raw_fields):
            if isinstance(f, str):
                f = {"name": f, "type": "email" if snake(f) == "email" else "text", "required": False}
            if not isinstance(f, dict):
                errors.append(f"{ename}.feld{j}: muss ein Objekt sein")
                continue
            fname = _ident(f.get("name"), f"{ename}.feld{j}", errors)
            if not fname or fname in RESERVED_FIELDS:
                continue  # implicit columns are generated automatically
            if fname in seen_fields:
                errors.append(f"{ename}.{fname}: doppelt")
                continue
            ftype = str(f.get("type", "text")).lower().strip()
            ftype = TYPE_ALIASES.get(ftype, ftype)
            ref = None
            if ftype.startswith("ref:"):
                ref = snake(ftype[4:])
                ftype = "ref"
            elif ftype not in FIELD_TYPES:
                errors.append(f"{ename}.{fname}: unbekannter Typ {ftype!r}")
                continue
            seen_fields.add(fname)
            fields.append({
                "name": fname, "type": ftype, "ref": ref,
                "required": bool(f.get("required", False)),
                "unique": bool(f.get("unique", False)),
                "max_length": int(f["max_length"]) if str(f.get("max_length", "")).isdigit() else None,
            })
        for rel in raw.get("relationships") or []:
            if isinstance(rel, dict) and rel.get("type") in ("n:1", "1:n", "1:1") and rel.get("target"):
                target = snake(str(rel["target"]))
                fk = _ident(rel.get("foreign_key") or f"{target}_id", f"{ename}.relation", errors)
                if fk and fk not in seen_fields and rel["type"] in ("n:1", "1:1"):
                    seen_fields.add(fk)
                    fields.append({"name": fk, "type": "ref", "ref": target, "required": False,
                                   "unique": rel["type"] == "1:1", "max_length": None})
        entities.append({"name": ename, "class_name": pascal(ename), "table": f"{ename}s"
                         if not ename.endswith("s") else ename, "fields": fields})

    for e in entities:
        for f in e["fields"]:
            if f["type"] == "ref" and f["ref"] not in seen_entities:
                errors.append(f"{e['name']}.{f['name']}: Referenz auf unbekannte Entität {f['ref']!r}")
    tables = [e["table"] for e in entities]
    if len(set(tables)) != len(tables):
        errors.append("Tabellennamen kollidieren (z.B. 'item' und 'items')")

    if errors:
        raise BlueprintError(errors)
    return {
        "name": name,
        "version": version,
        "description": _text(bp.get("description")),
        "entities": entities,
        "auth_method": _text(bp.get("auth_method"), 40) or "email_password",
        "pagination": "offset",
    }


def validate_blueprint(bp: Any) -> tuple[bool, list[str]]:
    try:
        normalize_blueprint(bp)
        return True, []
    except BlueprintError as e:
        return False, e.errors
