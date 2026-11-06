"""Blueprint template definition for NexusSaaS app creation."""
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

class FieldType(str, Enum):
    UUID = "uuid"
    TEXT = "text"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    JSONB = "jsonb"
    ENUM = "enum"

class RelationType(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:n"
    MANY_TO_MANY = "n:m"

class FieldDef(BaseModel):
    name: str
    type: FieldType
    required: bool = True
    unique: bool = False
    default: Optional[str] = None
    validation: Optional[str] = None

class RelationshipDef(BaseModel):
    type: RelationType
    target: str
    foreign_key: str

class EntityDef(BaseModel):
    name: str
    fields: list[FieldDef]
    relationships: list[RelationshipDef] = []
    soft_delete: bool = False
    tenant_scoped: bool = True

class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"

class PaginationType(str, Enum):
    CURSOR = "cursor"
    OFFSET = "offset"
    NONE = "none"

class EndpointDef(BaseModel):
    method: HttpMethod
    path: str
    description: str
    auth_required: bool = True
    roles: list[str] = ["viewer"]
    request_body: Optional[str] = None
    response_body: Optional[str] = None
    pagination: PaginationType = PaginationType.NONE
    rate_limit: Optional[str] = None

class AuthMethod(str, Enum):
    EMAIL_PASSWORD = "email_password"
    OAUTH_GOOGLE = "oauth_google"
    OAUTH_GITHUB = "oauth_github"
    MAGIC_LINK = "magic_link"
    API_KEY = "api_key"

class FrontendFramework(str, Enum):
    REACT = "react"
    VUE = "vue"
    SVELTE = "svelte"
    NONE = "none"

class PageDef(BaseModel):
    name: str
    path: str
    description: str
    auth_required: bool = True

class IntegrationDef(BaseModel):
    provider: str
    purpose: str
    config_keys: list[str] = []

class WebhookDef(BaseModel):
    event: str
    payload: Optional[str] = None
    retry_policy: Optional[str] = None

class NonFunctionalDef(BaseModel):
    expected_users: int = 100
    response_time_ms: int = 200
    uptime_sla: str = "99.9%"
    compliance: list[str] = []
    backup_strategy: str = "daily"
    monitoring: list[str] = ["metrics", "alerts", "logging"]

class BlueprintTemplate(BaseModel):
    name: str = Field(..., min_length=1)
    version: str = "1.0"
    description: str
    target_audience: str
    core_problem: str
    mvp_features: list[str] = []
    nice_to_have: list[str] = []
    entities: list[EntityDef] = []
    endpoints: list[EndpointDef] = []
    auth_method: AuthMethod = AuthMethod.EMAIL_PASSWORD
    roles: list[str] = ["owner", "admin", "member", "viewer"]
    permissions: dict = {}
    tenant_onboarding: str = "self_service"
    frontend_framework: FrontendFramework = FrontendFramework.REACT
    pages: list[PageDef] = []
    responsive: str = "mobile_first"
    dark_mode: bool = False
    i18n: list[str] = ["en"]
    integrations: list[IntegrationDef] = []
    webhooks_outbound: list[WebhookDef] = []
    non_functional: NonFunctionalDef = NonFunctionalDef()

# Query phases with beginner-friendly questions and 3 pre-formulated options
# Each option: (label, value, explanation)
QUERY_PHASES = [
    {
        "phase": 1,
        "name": "Vision & Scope",
        "questions": [
            {
                "id": "name",
                "question": "Wie soll deine App heißen?",
                "required": True,
                "type": "text",
                "hint": "Ein kurzer, einprägsamer Name (z.B. 'TaskFlow', 'MeinShop')",
                "options": None,
            },
            {
                "id": "description",
                "question": "Was macht deine App in einem Satz?",
                "required": True,
                "type": "text",
                "hint": "z.B. 'Ein Tool um Aufgaben im Team zu verwalten'",
                "options": None,
            },
            {
                "id": "target_audience",
                "question": "Wer nutzt die App?",
                "required": True,
                "type": "choice",
                "hint": "Wähle die passendste Option",
                "options": [
                    ("Nur ich / mein Team (klein, intern)", "internal_team", "Einfachste Option — keine Registrierung für externe nötig"),
                    ("Kleine Unternehmen / Freelancer", "small_business", "Braucht Login + einfache Rollen"),
                    ("Öffentlich für alle (B2C)", "public_b2c", "Braucht vollständige Registrierung + Skalierung"),
                ],
            },
            {
                "id": "core_problem",
                "question": "Welches Problem löst die App?",
                "required": True,
                "type": "text",
                "hint": "z.B. 'Aufgaben gehen in E-Mails verloren'",
                "options": None,
            },
            {
                "id": "mvp_features",
                "question": "Welche Funktionen braucht die App MINDESTENS?",
                "required": True,
                "type": "list",
                "hint": "Kommagetrennt, z.B. 'Aufgaben erstellen, zuweisen, Status ändern'",
                "options": [
                    ("Nur anzeigen + erstellen", "view_create", "Einfachste MVP-Option"),
                    ("Anzeigen, erstellen, bearbeiten, löschen", "crud", "Standard-CRUD — empfohlen"),
                    ("CRUD + Suche + Filter", "crud_search", "Mehr Komfort, etwas mehr Aufwand"),
                ],
            },
        ],
    },
    {
        "phase": 2,
        "name": "Datenmodell",
        "questions": [
            {
                "id": "entities",
                "question": "Welche Dinge (Objekte) verwaltet die App?",
                "required": True,
                "type": "list",
                "hint": "z.B. 'Aufgabe, Projekt, Benutzer, Kommentar'",
                "options": [
                    ("1-2 Objekte (z.B. Aufgabe, Benutzer)", "simple", "Einfachster Start"),
                    ("3-5 Objekte (z.B. Aufgabe, Projekt, Benutzer, Kommentar)", "medium", "Standard-App"),
                    ("6+ Objekte (komplexes System)", "complex", "Größeres Projekt"),
                ],
            },
            {
                "id": "tenant_scoped",
                "question": "Sollen Daten getrennt pro Nutzer/Firma gespeichert werden?",
                "required": True,
                "type": "choice",
                "hint": "Multi-Tenant = jeder Nutzer sieht nur seine Daten",
                "options": [
                    ("Nein, alle sehen alles (einfachste Option)", "no", "Für persönliche Apps oder Single-User"),
                    ("Ja, pro Nutzer getrennt", "per_user", "Standard für SaaS"),
                    ("Ja, pro Firma/Team getrennt", "per_org", "Für B2B mit Organisationen"),
                ],
            },
        ],
    },
    {
        "phase": 3,
        "name": "API & Zugriff",
        "questions": [
            {
                "id": "pagination",
                "question": "Wie sollen Listen angezeigt werden?",
                "required": True,
                "type": "choice",
                "hint": "Pagination = Aufteilen in Seiten",
                "options": [
                    ("Alles auf einmal laden (einfach, bis ~100 Einträge)", "none", "Einfachste Option für kleine Datenmengen"),
                    ("Seitenweise (10-50 pro Seite)", "offset", "Standard für die meisten Apps"),
                    ("Unendlich scrollen (wie Twitter/Instagram)", "cursor", "Beste UX, etwas komplexer"),
                ],
            },
            {
                "id": "rate_limit",
                "question": "Wie viele Anfragen pro Minute erlauben?",
                "required": True,
                "type": "choice",
                "hint": "Schützt vor Überlastung",
                "options": [
                    ("60 pro Minute (entspannt, reicht meist)", "60", "Für kleine Apps"),
                    ("120 pro Minute (Standard)", "120", "Für mittlere Apps"),
                    ("300 pro Minute (hoch, für APIs)", "300", "Für API-lastige Apps"),
                ],
            },
        ],
    },
    {
        "phase": 4,
        "name": "Login & Nutzer",
        "questions": [
            {
                "id": "auth_method",
                "question": "Wie sollen Nutzer sich einloggen?",
                "required": True,
                "type": "choice",
                "hint": "Wähle die einfachste Option",
                "options": [
                    ("E-Mail + Passwort (einfachste Option)", "email_password", "Keine externen Dienste nötig"),
                    ("Google Login (1 Klick für Nutzer)", "oauth_google", "Braucht Google Console Setup"),
                    ("Magic Link (Link per E-Mail)", "magic_link", "Kein Passwort, aber E-Mail-Service nötig"),
                ],
            },
            {
                "id": "tenant_onboarding",
                "question": "Wie kommen neue Nutzer zur App?",
                "required": True,
                "type": "choice",
                "hint": "Onboarding = Registrierung",
                "options": [
                    ("Jeder kann sich selbst registrieren (einfachste)", "self_service", "Offene Registrierung"),
                    ("Nur per Einladung (sicherer)", "invite_only", "Admin lädt ein"),
                    ("Admin erstellt Konten manuell (kontrolliert)", "admin_provisioned", "Für interne Tools"),
                ],
            },
        ],
    },
    {
        "phase": 5,
        "name": "Oberfläche",
        "questions": [
            {
                "id": "frontend",
                "question": "Braucht die App eine Weboberfläche?",
                "required": True,
                "type": "choice",
                "hint": "Frontend = was der Nutzer sieht",
                "options": [
                    ("Ja, mit React (modern, beliebt)", "react", "Beste Wahl für die meisten Apps"),
                    ("Ja, mit Vue (einfacher zu lernen)", "vue", "Guter Einstieg"),
                    ("Nein, nur API (Backend-only)", "none", "Für reine Backend-Services"),
                ],
            },
            {
                "id": "responsive",
                "question": "Soll die App auf dem Handy funktionieren?",
                "required": True,
                "type": "choice",
                "hint": "Responsive = passt sich an Bildschirmgröße an",
                "options": [
                    ("Ja, Handy zuerst (Mobile-First)", "mobile_first", "Für Apps die mobil genutzt werden"),
                    ("Ja, Desktop zuerst (Desktop-First)", "desktop_first", "Für Büro-Apps"),
                    ("Nur Desktop (kein Mobile)", "desktop_only", "Einfachste Option"),
                ],
            },
            {
                "id": "dark_mode",
                "question": "Dark Mode (dunkles Design)?",
                "required": False,
                "type": "choice",
                "hint": "Dunkles Farbschema",
                "options": [
                    ("Ja, mit Umschalter", "yes", "Nutzer kann wählen"),
                    ("Nein, nur helles Design", "no", "Einfachste Option"),
                    ("Automatisch (folgt System-Einstellung)", "auto", "Kein Button nötig"),
                ],
            },
        ],
    },
    {
        "phase": 6,
        "name": "Extras & Integrationen",
        "questions": [
            {
                "id": "integrations",
                "question": "Braucht die App externe Dienste?",
                "required": False,
                "type": "choice",
                "hint": "Zahlungen, E-Mails, Dateispeicher",
                "options": [
                    ("Keine (einfachste Option)", "none", "Nur die App selbst"),
                    ("E-Mail-Versand (z.B. SendGrid)", "email", "Für Benachrichtigungen"),
                    ("Zahlungen (Stripe)", "stripe", "Für kostenpflichtige Apps"),
                ],
            },
            {
                "id": "i18n",
                "question": "Mehrsprachig?",
                "required": False,
                "type": "choice",
                "hint": "Internationalisierung",
                "options": [
                    ("Nur Deutsch", "de", "Einfachste Option"),
                    ("Deutsch + Englisch", "de,en", "Für internationale Nutzer"),
                    ("Englisch only", "en", "Für englischsprachige Zielgruppe"),
                ],
            },
        ],
    },
    {
        "phase": 7,
        "name": "Größe & Sicherheit",
        "questions": [
            {
                "id": "expected_users",
                "question": "Wie viele Nutzer erwartest du?",
                "required": True,
                "type": "choice",
                "hint": "Beeinflusst die Infrastruktur",
                "options": [
                    ("Unter 100 (klein, günstig)", "100", "Kleiner Server reicht"),
                    ("100-1.000 (mittel)", "1000", "Standard-Setup"),
                    ("Über 1.000 (groß)", "10000", "Skalierbare Infrastruktur nötig"),
                ],
            },
            {
                "id": "compliance",
                "question": "Datenschutz-Anforderungen?",
                "required": True,
                "type": "choice",
                "hint": "DSGVO = EU-Datenschutz",
                "options": [
                    ("DSGVO (Standard für EU)", "gdpr", "Für Apps mit EU-Nutzern"),
                    ("DSGVO + keine besonderen Anforderungen", "gdpr_basic", "Einfachste Option"),
                    ("HIPAA (Gesundheitsdaten, USA)", "hipaa", "Für medizinische Apps"),
                ],
            },
        ],
    },
]
