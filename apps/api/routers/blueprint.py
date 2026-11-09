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
3. Welche 6 spezifischen Folgefragen (mit Fragezeichen) sollten gestellt werden? Generiere 6 echte Fragen die mit ? enden. NICHT allgemeine Fragen.

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
    
    # Try to parse JSON from response - handle nested JSON strings
    try:
        # Find the outermost JSON
        # Strip markdown code blocks
        response = response.strip()
        if '```' in response:
            parts = response.split('```')
            if len(parts) >= 2:
                response = parts[1]
            if response.startswith('json'):
                response = response[4:]
        response = response.strip()
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            data = json.loads(json_str)
            
            # The LLM might return research as a JSON string - parse it (one level only)
            research_raw = data.get("research", "")
            follow_ups = data.get("follow_up_questions", [])
            sources = data.get("sources", [])
            
            if isinstance(research_raw, str) and research_raw.strip().startswith('{'):
                try:
                    inner = json.loads(research_raw)
                    # Extract research text (don't recurse)
                    r = inner.get("research", "")
                    if isinstance(r, str) and not r.strip().startswith('{'):
                        research = r
                    else:
                        research = research_raw
                    if not sources:
                        sources = inner.get("sources", [])
                    if not follow_ups:
                        follow_ups = inner.get("follow_up_questions", [])
                except json.JSONDecodeError:
                    research = research_raw
            else:
                research = research_raw
            
            if not research:
                research = "Recherche abgeschlossen"
            
            # Clean up follow-up questions - only actual questions
            clean_followups = []
            for fq in follow_ups:
                if isinstance(fq, dict) and fq.get("q"):
                    q_text = fq.get("q", "").strip()
                    # Ensure it's a real question (contains ? or starts with question word)
                    if '?' not in q_text and not any(q_text.lower().startswith(w) for w in ['wie', 'was', 'welche', 'soll', 'braucht', 'gibt', 'moechtest', 'willst']):
                        q_text = q_text + '?'
                    fq["q"] = q_text
                    clean_followups.append({
                        "id": fq.get("id", "fq_" + str(len(clean_followups))),
                        "q": fq.get("q", ""),
                        "hint": fq.get("hint", ""),
                        "type": fq.get("type", "text"),
                        "options": fq.get("options", None)
                    })
            
            return {
                "question_id": question_id,
                "answer": answer,
                "research": research if research else "Recherche abgeschlossen",
                "sources": sources if sources else ["NexusSaaS Blueprint Engine"],
                "follow_up_questions": clean_followups
            }
    except (json.JSONDecodeError, Exception) as e:
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
