"""Backend code generation from a normalized blueprint.

Output is a complete FastAPI + SQLAlchemy project (multi-tenant CRUD API, SQL
migration, tests). Generation is template-based and deterministic: the same
blueprint always yields byte-identical files. Only identifiers validated by
``normalize_blueprint`` are interpolated; free text goes through ``repr``.
"""
from __future__ import annotations

from packages.blueprint.ddl import generate_ddl

GENERATOR_VERSION = "1.0.0"

SA_TYPES = {
    "text": "Text", "integer": "Integer", "float": "Float", "boolean": "Boolean",
    "timestamp": "DateTime(timezone=True)", "date": "Date", "uuid": "Uuid", "jsonb": "JSON",
    "email": "String(320)", "ref": "Uuid",
}
PY_TYPES = {
    "text": "str", "integer": "int", "float": "float", "boolean": "bool", "timestamp": "datetime",
    "date": "date", "uuid": "uuid.UUID", "jsonb": "Any", "email": "str", "ref": "uuid.UUID",
}
SAMPLES = {
    "text": '"Beispiel"', "integer": "42", "float": "1.5", "boolean": "True",
    "timestamp": '"2026-01-01T12:00:00+00:00"', "date": '"2026-01-01"',
    "uuid": '"00000000-0000-0000-0000-0000000000aa"', "jsonb": '{"k": "v"}',
    "email": '"max@example.com"',
}
UPDATE_SAMPLES = {
    "text": '"Geaendert"', "integer": "7", "float": "2.5", "boolean": "False",
    "timestamp": '"2026-02-01T12:00:00+00:00"', "date": '"2026-02-01"',
    "uuid": '"00000000-0000-0000-0000-0000000000bb"', "jsonb": '{"k": "w"}',
    "email": '"erika@example.com"',
}
REQUIREMENTS = """fastapi==0.115.6
uvicorn==0.34.0
sqlalchemy==2.0.36
pydantic==2.10.4
psycopg2-binary==2.9.10
httpx==0.28.1
pytest==8.3.4
"""


def _sa_column(f: dict, tables: dict) -> str:
    t = SA_TYPES[f["type"]]
    if f["type"] == "text" and f.get("max_length"):
        t = f"String({int(f['max_length'])})"
    args = [t]
    if f["type"] == "ref":
        args.append(f'ForeignKey("{tables[f["ref"]]}.id", ondelete="SET NULL")')
    kw = [f"nullable={not (f['required'] and f['type'] != 'ref')}"]
    if f["type"] == "ref":
        kw.append("index=True")
    return f"    {f['name']} = Column({', '.join(args + kw)})"


def _pyd_field(f: dict, optional: bool) -> str:
    py = PY_TYPES[f["type"]]
    constraints = []
    if f["type"] == "email":
        constraints += [r'pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"', "max_length=320"]
    elif f["type"] == "text":
        constraints.append(f"max_length={int(f['max_length']) if f.get('max_length') else 10000}")
    required = f["required"] and f["type"] != "ref" and not optional
    default = "..." if required else "None"
    ann = py if required else f"Optional[{py}]"
    if constraints:
        return f"    {f['name']}: {ann} = Field({default}, {', '.join(constraints)})"
    return f"    {f['name']}: {ann} = {default}"


def _models(bp: dict) -> str:
    tables = {e["name"]: e["table"] for e in bp["entities"]}
    lines = [
        '"""SQLAlchemy models (generated). Every row belongs to exactly one tenant."""',
        "import uuid",
        "from datetime import datetime, timezone",
        "",
        "from sqlalchemy import (  # noqa: F401",
        "    JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid,",
        ")",
        "",
        "from app.db import Base",
        "",
        "",
        "def _now():",
        "    return datetime.now(timezone.utc)",
        "",
    ]
    for e in bp["entities"]:
        uniques = [f for f in e["fields"] if f["unique"]]
        lines += ["", f"class {e['class_name']}(Base):", f'    __tablename__ = "{e["table"]}"']
        if uniques:
            cons = ", ".join(f'UniqueConstraint("tenant_id", "{f["name"]}", name="uq_{e["table"]}_{f["name"]}")'
                             for f in uniques)
            lines.append(f"    __table_args__ = ({cons},)")
        lines += [
            "    id = Column(Uuid, primary_key=True, default=uuid.uuid4)",
            "    tenant_id = Column(Uuid, nullable=False, index=True)",
        ]
        lines += [_sa_column(f, tables) for f in e["fields"]]
        lines += [
            "    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)",
            "    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)",
        ]
    return "\n".join(lines) + "\n"


def _schemas(bp: dict) -> str:
    lines = [
        '"""Pydantic schemas (generated)."""',
        "import uuid",
        "from datetime import date, datetime  # noqa: F401",
        "from typing import Any, Optional  # noqa: F401",
        "",
        "from pydantic import BaseModel, ConfigDict, Field  # noqa: F401",
        "",
    ]
    for e in bp["entities"]:
        c = e["class_name"]
        create = [_pyd_field(f, optional=False) for f in e["fields"]]
        update = [_pyd_field(f, optional=True) for f in e["fields"]]
        out = [f"    {f['name']}: Optional[{PY_TYPES[f['type']]}] = None" for f in e["fields"]]
        lines += ["", f"class {c}Create(BaseModel):", '    model_config = ConfigDict(extra="forbid")', *create,
                  "", "", f"class {c}Update(BaseModel):", '    model_config = ConfigDict(extra="forbid")', *update,
                  "", "", f"class {c}Out(BaseModel):", "    model_config = ConfigDict(from_attributes=True)",
                  "    id: uuid.UUID", *out, "    created_at: datetime", "    updated_at: datetime", "",
                  "", f"class {c}Page(BaseModel):", f"    items: list[{c}Out]", "    total: int",
                  "    limit: int", "    offset: int", ""]
    return "\n".join(lines) + "\n"


def _routes(bp: dict) -> str:
    by_name = {e["name"]: e for e in bp["entities"]}
    lines = [
        '"""CRUD routes (generated). All queries are filtered by the caller\'s tenant."""',
        "import uuid",
        "",
        "from fastapi import APIRouter, Depends, HTTPException, Query, Response",
        "from sqlalchemy.orm import Session",
        "",
        "from app import models, schemas",
        "from app.db import get_session, get_tenant_id",
        "",
        "router = APIRouter()",
        "",
        "",
        "def _check_ref(db: Session, model, ref_id, tenant_id, field: str):",
        "    if ref_id is None:",
        "        return",
        "    found = db.query(model.id).filter(model.id == ref_id, model.tenant_id == tenant_id).first()",
        "    if found is None:",
        '        raise HTTPException(422, f"{field}: referenced object not found")',
        "",
    ]
    for e in bp["entities"]:
        c, n, t = e["class_name"], e["name"], e["table"]
        refs = [f for f in e["fields"] if f["type"] == "ref"]
        ref_checks = [f"    _check_ref(db, models.{by_name[f['ref']]['class_name']}, data.get({f['name']!r}), "
                      f"tenant_id, {f['name']!r})" for f in refs]
        lines += [
            "",
            f'@router.get("/{t}", response_model=schemas.{c}Page, tags=["{t}"])',
            f"def list_{t}(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),",
            "             db: Session = Depends(get_session), tenant_id: uuid.UUID = Depends(get_tenant_id)):",
            f"    q = db.query(models.{c}).filter(models.{c}.tenant_id == tenant_id)",
            "    total = q.count()",
            f"    items = q.order_by(models.{c}.created_at, models.{c}.id).offset(offset).limit(limit).all()",
            f"    return schemas.{c}Page(items=items, total=total, limit=limit, offset=offset)",
            "",
            "",
            f'@router.post("/{t}", response_model=schemas.{c}Out, status_code=201, tags=["{t}"])',
            f"def create_{n}(body: schemas.{c}Create, db: Session = Depends(get_session),",
            "             tenant_id: uuid.UUID = Depends(get_tenant_id)):",
            "    data = body.model_dump()",
            *ref_checks,
            f"    obj = models.{c}(tenant_id=tenant_id, **data)",
            "    db.add(obj)",
            "    db.commit()",
            "    db.refresh(obj)",
            "    return obj",
            "",
            "",
            f"def _get_{n}(db: Session, tenant_id: uuid.UUID, obj_id: uuid.UUID):",
            f"    obj = db.query(models.{c}).filter(models.{c}.id == obj_id, models.{c}.tenant_id == tenant_id).first()",
            "    if obj is None:",
            f'        raise HTTPException(404, "{c} not found")',
            "    return obj",
            "",
            "",
            f'@router.get("/{t}/{{obj_id}}", response_model=schemas.{c}Out, tags=["{t}"])',
            f"def get_{n}(obj_id: uuid.UUID, db: Session = Depends(get_session),",
            "          tenant_id: uuid.UUID = Depends(get_tenant_id)):",
            f"    return _get_{n}(db, tenant_id, obj_id)",
            "",
            "",
            f'@router.patch("/{t}/{{obj_id}}", response_model=schemas.{c}Out, tags=["{t}"])',
            f"def update_{n}(obj_id: uuid.UUID, body: schemas.{c}Update, db: Session = Depends(get_session),",
            "             tenant_id: uuid.UUID = Depends(get_tenant_id)):",
            f"    obj = _get_{n}(db, tenant_id, obj_id)",
            "    data = body.model_dump(exclude_unset=True)",
            *ref_checks,
            "    for key, value in data.items():",
            "        setattr(obj, key, value)",
            "    db.commit()",
            "    db.refresh(obj)",
            "    return obj",
            "",
            "",
            f'@router.delete("/{t}/{{obj_id}}", status_code=204, tags=["{t}"])',
            f"def delete_{n}(obj_id: uuid.UUID, db: Session = Depends(get_session),",
            "             tenant_id: uuid.UUID = Depends(get_tenant_id)):",
            f"    db.delete(_get_{n}(db, tenant_id, obj_id))",
            "    db.commit()",
            "    return Response(status_code=204)",
            "",
        ]
    return "\n".join(lines) + "\n"


DB_PY = '''"""Database session and tenant context (generated).

Replace ``get_tenant_id`` with your real authentication (e.g. a verified JWT claim).
The X-Tenant-ID header is a development placeholder and must not be trusted in production.
"""
import os
import uuid
from typing import Iterator

from fastapi import Depends, Header, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
_kwargs = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def get_tenant_id(x_tenant_id: str = Header(...)) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(400, "invalid X-Tenant-ID")


def get_session(tenant_id: uuid.UUID = Depends(get_tenant_id)) -> Iterator[Session]:
    db = SessionLocal()
    try:
        if engine.dialect.name == "postgresql":
            db.execute(text("SELECT set_config('app.tenant_id', :t, false)"), {"t": str(tenant_id)})
        yield db
    finally:
        if engine.dialect.name == "postgresql":
            db.execute(text("RESET app.tenant_id"))
        db.close()
'''


def _main(bp: dict) -> str:
    return "\n".join([
        f'"""{bp["name"]} API (generated by NexusSaaS {GENERATOR_VERSION})."""',
        "from contextlib import asynccontextmanager",
        "",
        "from fastapi import FastAPI",
        "",
        "from app.db import Base, engine",
        "from app.routes import router",
        "",
        "",
        "@asynccontextmanager",
        "async def lifespan(_app):",
        '    if engine.dialect.name == "sqlite":  # PostgreSQL uses migrations/001_init.sql',
        "        Base.metadata.create_all(engine)",
        "    yield",
        "",
        "",
        f"app = FastAPI(title={bp['name']!r}, version={bp['version']!r}, description={bp['description']!r},",
        "              lifespan=lifespan)",
        "app.include_router(router)",
        "",
        "",
        '@app.get("/healthz")',
        "def healthz():",
        '    return {"status": "ok"}',
        "",
    ])


def _tests(bp: dict) -> str:
    lines = [
        '"""Generated API tests: CRUD and tenant isolation for every entity."""',
        "import os",
        "import uuid",
        "",
        'os.environ["DATABASE_URL"] = "sqlite:////tmp/generated-test.db"',
        "",
        "import pytest  # noqa: E402",
        "from fastapi.testclient import TestClient  # noqa: E402",
        "",
        "from app.db import Base, engine  # noqa: E402",
        "from app.main import app  # noqa: E402",
        "",
        "",
        "@pytest.fixture(autouse=True)",
        "def _db():",
        "    Base.metadata.drop_all(engine)",
        "    Base.metadata.create_all(engine)",
        "    yield",
        "",
        "",
        "@pytest.fixture",
        "def client():",
        "    return TestClient(app)",
        "",
        "",
        "def tenant():",
        '    return {"X-Tenant-ID": str(uuid.uuid4())}',
        "",
        "",
        "def test_healthz(client):",
        '    assert client.get("/healthz").json() == {"status": "ok"}',
        "",
        "",
        "def test_tenant_header_required(client):",
        f'    assert client.get("/{bp["entities"][0]["table"]}").status_code == 422',
        "",
    ]
    by_name = {e["name"]: e for e in bp["entities"]}

    def payload_of(ent: dict) -> str:
        return ", ".join(f"{f['name']!r}: {SAMPLES[f['type']]}" for f in ent["fields"] if f["type"] != "ref")

    for e in bp["entities"]:
        t, n = e["table"], e["name"]
        payload = payload_of(e)
        sep = ", " if payload else ""
        upd = [f for f in e["fields"] if f["type"] != "ref"]
        lines += [
            "",
            f"def test_{n}_crud(client):",
            "    h = tenant()",
            f'    r = client.post("/{t}", json={{{payload}}}, headers=h)',
            "    assert r.status_code == 201, r.text",
            '    obj_id = r.json()["id"]',
            f'    assert client.get(f"/{t}/{{obj_id}}", headers=h).status_code == 200',
            f'    page = client.get("/{t}", headers=h).json()',
            '    assert page["total"] == 1 and page["items"][0]["id"] == obj_id',
        ]
        if upd:
            f = upd[0]
            lines += [
                f'    r = client.patch(f"/{t}/{{obj_id}}", json={{{f["name"]!r}: {UPDATE_SAMPLES[f["type"]]}}}, '
                "headers=h)",
                "    assert r.status_code == 200, r.text",
            ]
        lines += [
            f'    assert client.delete(f"/{t}/{{obj_id}}", headers=h).status_code == 204',
            f'    assert client.get(f"/{t}/{{obj_id}}", headers=h).status_code == 404',
            "",
            "",
            f"def test_{n}_tenant_isolation(client):",
            "    a, b = tenant(), tenant()",
            f'    obj_id = client.post("/{t}", json={{{payload}}}, headers=a).json()["id"]',
            f'    assert client.get(f"/{t}/{{obj_id}}", headers=b).status_code == 404',
            f'    assert client.get("/{t}", headers=b).json()["total"] == 0',
            f'    assert client.delete(f"/{t}/{{obj_id}}", headers=b).status_code == 404',
            f'    assert client.get(f"/{t}/{{obj_id}}", headers=a).status_code == 200',
            "",
            "",
            f"def test_{n}_rejects_unknown_fields(client):",
            f'    r = client.post("/{t}", json={{{payload}{sep}"not_a_field": 1}}, headers=tenant())',
            "    assert r.status_code == 422",
            "",
        ]
        for f in e["fields"]:
            if f["type"] != "ref":
                continue
            target = by_name[f["ref"]]
            tp = payload_of(target)
            lines += [
                "",
                f"def test_{n}_{f['name']}_cross_tenant_reference_rejected(client):",
                "    a, b = tenant(), tenant()",
                f'    foreign = client.post("/{target["table"]}", json={{{tp}}}, headers=b).json()["id"]',
                f'    r = client.post("/{t}", json={{{payload}{sep}{f["name"]!r}: foreign}}, headers=a)',
                "    assert r.status_code == 422",
                f'    own = client.post("/{target["table"]}", json={{{tp}}}, headers=a).json()["id"]',
                f'    r = client.post("/{t}", json={{{payload}{sep}{f["name"]!r}: own}}, headers=a)',
                "    assert r.status_code == 201, r.text",
                "",
            ]
    return "\n".join(lines) + "\n"


def _readme(bp: dict) -> str:
    ents = "\n".join(f"- `{e['table']}`: " + (", ".join(f"{f['name']} ({f['type']})" for f in e["fields"]) or "-")
                     for e in bp["entities"])
    return f"""# {bp['name']}

{bp['description'] or 'Generated by NexusSaaS.'}

Generated by NexusSaaS code generator {GENERATOR_VERSION}. Blueprint version {bp['version']}.

## Entities

{ents}

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload       # SQLite by default
pytest -q
```

For PostgreSQL apply `migrations/001_init.sql` and set `DATABASE_URL`.
Each table is protected by row-level security on `app.tenant_id`.

## Before production

- Replace the `X-Tenant-ID` placeholder in `app/db.py` with real authentication.
- Review the generated code and `SECURITY_REPORT.json` shipped with this package.
"""


DOCKERFILE = """FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER nobody
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""


def generate_backend(bp: dict) -> dict[str, str]:
    """Return {relative_path: content} for a normalized blueprint."""
    return {
        "README.md": _readme(bp),
        "requirements.txt": REQUIREMENTS,
        "Dockerfile": DOCKERFILE,
        "app/__init__.py": "",
        "app/db.py": DB_PY,
        "app/models.py": _models(bp),
        "app/schemas.py": _schemas(bp),
        "app/routes.py": _routes(bp),
        "app/main.py": _main(bp),
        "migrations/001_init.sql": generate_ddl(bp),
        "tests/__init__.py": "",
        "tests/test_api.py": _tests(bp),
        "pytest.ini": "[pytest]\naddopts = -p no:cacheprovider\ntestpaths = tests\n",
    }
