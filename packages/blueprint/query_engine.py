"""Step-by-step blueprint query engine for NexusSaaS."""
from packages.blueprint.template import QUERY_PHASES, BlueprintTemplate

class BlueprintQueryEngine:
    """Interactive blueprint creation through step-by-step questioning."""

    def __init__(self):
        self.current_phase = 0
        self.current_question = 0
        self.answers = {}
        self.completed = False

    def get_next_question(self) -> dict | None:
        """Get the next unanswered question."""
        while self.current_phase < len(QUERY_PHASES):
            phase = QUERY_PHASES[self.current_phase]
            questions = phase["questions"]
            while self.current_question < len(questions):
                q = questions[self.current_question]
                if q["id"] not in self.answers:
                    return {
                        "phase": phase["phase"],
                        "phase_name": phase["name"],
                        "question_id": q["id"],
                        "question": q["question"],
                        "required": q["required"],
                        "type": q["type"],
                        "hint": q.get("hint", ""),
                        "options": q.get("options"),
                        "choices": q.get("choices"),
                    }
                self.current_question += 1
            self.current_phase += 1
            self.current_question = 0
        self.completed = True
        return None

    def submit_answer(self, question_id: str, answer: str) -> dict:
        """Submit an answer and validate it."""
        # Find the question
        q = None
        for phase in QUERY_PHASES:
            for question in phase["questions"]:
                if question["id"] == question_id:
                    q = question
                    break
            if q:
                break

        if not q:
            return {"error": f"Unknown question: {question_id}"}

        # Validate
        if q["required"] and not answer.strip():
            return {"error": "This field is required"}

        # Parse based on type
        if q["type"] == "list":
            self.answers[question_id] = [a.strip() for a in answer.split(",") if a.strip()]
        elif q["type"] == "boolean":
            self.answers[question_id] = answer.lower() in ("ja", "yes", "true", "1")
        elif q["type"] == "number":
            try:
                self.answers[question_id] = int(answer)
            except ValueError:
                return {"error": "Must be a number"}
        else:
            self.answers[question_id] = answer.strip()

        # Advance
        self.current_question += 1
        return {"status": "accepted", "next": self.get_next_question()}

    def get_progress(self) -> dict:
        """Get current progress."""
        total = sum(len(p["questions"]) for p in QUERY_PHASES)
        answered = len(self.answers)
        return {
            "phase": self.current_phase + 1,
            "total_phases": len(QUERY_PHASES),
            "answered": answered,
            "total": total,
            "percentage": round(answered / total * 100, 1),
            "completed": self.completed,
        }

    def generate_blueprint(self) -> dict:
        """Generate blueprint from collected answers."""
        if not self.completed:
            return {"error": "Not all questions answered yet"}

        # Map answers to blueprint structure
        blueprint = {
            "name": self.answers.get("name", ""),
            "version": "1.0",
            "description": self.answers.get("description", ""),
            "target_audience": self.answers.get("target_audience", ""),
            "core_problem": self.answers.get("core_problem", ""),
            "mvp_features": self.answers.get("mvp_features", []),
            "nice_to_have": self.answers.get("nice_to_have", []),
            "entities": [],
            "endpoints": [],
            "auth_method": self.answers.get("auth_method", "email_password"),
            "roles": self.answers.get("roles", ["owner", "admin", "member", "viewer"]),
            "tenant_onboarding": self.answers.get("tenant_onboarding", "self_service"),
            "frontend_framework": self.answers.get("frontend", "react"),
            "pages": [{"name": p, "path": f"/{p.lower().replace(' ', '-')}", "description": p, "auth_required": True} for p in self.answers.get("pages", [])],
            "responsive": self.answers.get("responsive", "mobile_first"),
            "dark_mode": self.answers.get("dark_mode", False),
            "i18n": self.answers.get("i18n", ["en"]),
            "integrations": [{"provider": i, "purpose": i, "config_keys": []} for i in self.answers.get("integrations", [])],
            "webhooks_outbound": [{"event": e, "payload": None, "retry_policy": "exponential"} for e in self.answers.get("webhooks_outbound", [])],
            "non_functional": {
                "expected_users": self.answers.get("expected_users", 100),
                "response_time_ms": self.answers.get("response_time", 200),
                "uptime_sla": "99.9%",
                "compliance": self.answers.get("compliance", []),
                "backup_strategy": self.answers.get("backup", "daily"),
                "monitoring": ["metrics", "alerts", "logging"],
            },
        }
        return blueprint
