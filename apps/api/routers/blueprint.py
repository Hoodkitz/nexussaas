"""Guided blueprint creation for the Matrix app: research per answer and a draft blueprint.

All endpoints require login (they call an LLM). LLM output is untrusted: questions
are length-limited plain text and drafts must pass normalize_blueprint.
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.deps import Principal, require
from packages.blueprint.schema import BlueprintError, normalize_blueprint, snake
from packages.llm import complete_json

router = APIRouter(prefix="/blueprint", tags=["blueprint"])

FIRST_QUESTION = {
    "id": "app_description",
    "q": "Was soll deine App machen? Beschreibe in eigenen Worten.",
    "hint": "z.B. 'Ein Dienstplan für die Bundeswehr' oder 'Ein Tool um Aufgaben im Team zu verwalten'",
    "type": "text",
    "options": None,
}


class ResearchIn(BaseModel):
    question_id: str = Field(max_length=100)
    question: str = Field(default="", max_length=500)
    answer: str = Field(max_length=2000)
    context: dict[str, str] = Field(default_factory=dict)


class DraftIn(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


def _clip(v, n: int) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def _context(answers: dict[str, str]) -> str:
    items = list(answers.items())[:30]
    return "\n".join(f"- {_clip(k, 60)}: {_clip(v, 300)}" for k, v in items)


def _clean_questions(raw) -> list[dict]:
    out = []
    for i, fq in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(fq, dict) or not fq.get("q"):
            continue
        q = _clip(fq["q"], 200)
        if not q.endswith("?"):
            q += "?"
        opts = None
        if isinstance(fq.get("options"), list):
            opts = [[_clip(o[0], 80), _clip(o[1], 40), _clip(o[2] if len(o) > 2 else "", 120)]
                    for o in fq["options"][:4] if isinstance(o, list) and len(o) >= 2]
        out.append({"id": snake(_clip(fq.get("id") or f"fq_{i}", 40)) or f"fq_{i}", "q": q,
                    "hint": _clip(fq.get("hint"), 160), "type": "choice" if opts else "text", "options": opts})
        if len(out) >= 4:
            break
    return out


@router.get("/next-question")
def next_question(p: Principal = Depends(require("read"))):
    return FIRST_QUESTION


@router.post("/research")
async def research(req: ResearchIn, p: Principal = Depends(require("read"))):
    prompt = f"""Du hilfst Laien, eine App zu planen. Bisherige Antworten:
{_context(req.context)}

Neue Frage: {_clip(req.question or req.question_id, 300)}
Antwort: {_clip(req.answer, 1000)}

Gib JSON zurück:
{{"research": "2-3 Sätze: was die Antwort für Daten und Funktionen der App bedeutet",
 "follow_up_questions": [{{"id": "kurz_snake_case", "q": "konkrete Frage zu Daten oder Abläufen?",
   "hint": "kurzer Hinweis", "options": [["Option", "wert", "Erklärung"]]}}]}}
Höchstens 3 Folgefragen, nur wenn wirklich Informationen für das Datenmodell fehlen. Deutsch."""
    data = await complete_json(prompt)
    if not data:
        return {"research": "Antwort gespeichert (KI gerade nicht erreichbar).", "follow_up_questions": [],
                "ai": False}
    return {"research": _clip(data.get("research") or "Analyse abgeschlossen.", 600),
            "follow_up_questions": _clean_questions(data.get("follow_up_questions")), "ai": True}


def _fallback(answers: dict[str, str]) -> dict:
    desc = _clip(answers.get("app_description"), 300) or "Meine App"
    name = snake(" ".join(desc.split()[:3])) or "meine_app"
    if not re.match(r"^[a-z]", name):
        name = "app_" + name
    return {"name": name[:40], "version": "1.0", "description": desc, "entities": [
        {"name": "item", "fields": [{"name": "title", "type": "text", "required": True, "max_length": 200},
                                    {"name": "description", "type": "text"},
                                    {"name": "status", "type": "text", "max_length": 40},
                                    {"name": "due_date", "type": "date"}]}]}


@router.post("/draft")
async def draft(req: DraftIn, p: Principal = Depends(require("read"))):
    """Turn questionnaire answers into a validated blueprint the user can submit as a job."""
    if not req.answers:
        raise HTTPException(422, "Keine Antworten")
    prompt = f"""Erstelle aus diesen Antworten ein Datenmodell für eine Web-API:
{_context(req.answers)}

Gib NUR JSON in genau diesem Format zurück:
{{"name": "app_name_snake_case", "version": "1.0", "description": "ein Satz",
 "entities": [{{"name": "entity_snake_case", "fields": [
   {{"name": "field_snake_case", "type": "text|integer|float|boolean|timestamp|date|email|json|ref:<entity>",
     "required": true, "unique": false}}]}}]}}
Regeln: 2 bis 8 Entitäten, je 2 bis 12 Felder, keine Felder id/tenant_id/created_at/updated_at,
Beziehungen als Feld "<entity>_id" mit type "ref:<entity>". Englische snake_case-Namen."""
    data = await complete_json(prompt, timeout=90)
    source = "ai"
    bp = None
    if data:
        try:
            normalize_blueprint(data)
            bp = {k: data[k] for k in ("name", "version", "description", "entities") if k in data}
        except BlueprintError:
            bp = None
    if bp is None:
        bp, source = _fallback(req.answers), "fallback"
    normalized = normalize_blueprint(bp)
    if len(json.dumps(bp)) > 200_000:
        raise HTTPException(413, "Blueprint zu groß")
    return {"blueprint": bp, "source": source,
            "summary": {e["table"]: [f["name"] for f in e["fields"]] for e in normalized["entities"]}}
