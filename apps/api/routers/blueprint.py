

@router.post("/research")
async def research_answer(question_id: str, answer: str):
    """AI researches what an answer means for app creation."""
    import os
    # Use environment variable for API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    # For now, return structured research prompt
    research_prompt = f"""
    User answered question '{question_id}' with: '{answer}'
    
    Research:
    1. What does this mean for app creation?
    2. What sources/data are needed?
    3. What follow-up questions should be asked?
    4. What specific requirements does this create?
    """
    return {
        "question_id": question_id,
        "answer": answer,
        "research_prompt": research_prompt,
        "follow_up_questions": [
            f"Basierend auf deiner Antwort '{answer}': Welche spezifischen Anforderungen gibt es?",
            "Welche Datenquellen oder Vorschriften sind relevant?",
            "Gibt es besondere Regeln oder Einschränkungen?"
        ]
    }
