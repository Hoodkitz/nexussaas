import os
import json
import httpx
from fastapi import APIRouter, Query

router = APIRouter(prefix="/blueprint", tags=["blueprint"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

QUESTIONS_DB = {
    "initial": {
        "id": "app_description",
        "q": "Was soll deine App machen? Beschreibe in eigenen Worten.",
        "hint": "z.B. 'Ein Dienstplan für die Bundeswehr' oder 'Ein Tool um Aufgaben im Team zu verwalten'",
        "type": "text"
    }
}


async def call_ollama(prompt: str) -> str:
    """Call Ollama for real AI research."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.2:1b",
                    "prompt": prompt,
                    "stream": False
                }
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
    except Exception as e:
        return f"Error: {str(e)}"
    return ""


@router.post("/research")
async def research_answer(question_id: str = Query(...), answer: str = Query(...)):
    """AI researches what an answer means and generates follow-up questions."""
    
    prompt = f"""Du bist ein Experte für App-Entwicklung. Ein Nutzer hat auf die Frage '{question_id}' geantwortet: '{answer}'.

Recherchiere:
1. Was bedeutet diese Antwort für die App-Erstellung?
2. Welche Daten/Quellen/Vorschriften sind relevant?
3. Welche 3-5 spezifischen Folgefragen sollten gestellt werden, um die App besser zu verstehen?

Antworte im JSON-Format:
{{
  "research": "Deine Recherche-Ergebnisse in 2-3 Sätzen",
  "sources": ["Quelle 1", "Quelle 2"],
  "follow_up_questions": [
    {{"id": "unique_id", "q": "Frage text", "hint": "Hinweis", "type": "text oder choice", "options": [["Option 1", "val1", "Beschreibung"], ["Option 2", "val2", "Beschreibung"]]}}
  ]
}}

Nur JSON, keine anderen Texte."""

    response = await call_ollama(prompt)
    
    # Try to parse JSON from response
    try:
        # Find JSON in response
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            return {
                "question_id": question_id,
                "answer": answer,
                "research": data.get("research", "Recherche abgeschlossen"),
                "sources": data.get("sources", []),
                "follow_up_questions": data.get("follow_up_questions", [])
            }
    except json.JSONDecodeError:
        pass
    
    # Fallback: return raw response
    return {
        "question_id": question_id,
        "answer": answer,
        "research": response[:500] if response else "Recherche abgeschlossen",
        "sources": ["NexusSaaS Blueprint Engine"],
        "follow_up_questions": []
    }


@router.get("/next-question")
async def get_next_question(context: str = Query("")):
    """Get the next question based on context."""
    return QUESTIONS_DB["initial"]
