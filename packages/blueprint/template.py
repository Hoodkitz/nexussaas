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
    """Complete blueprint template for app creation."""
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

# Query phases for step-by-step blueprint creation
QUERY_PHASES = [
    {
        "phase": 1,
        "name": "Vision & Scope",
        "questions": [
            {"id": "name", "question": "Wie heißt die App?", "required": True, "type": "text"},
            {"id": "description", "question": "Kurzbeschreibung in einem Satz?", "required": True, "type": "text"},
            {"id": "target_audience", "question": "Wer nutzt die App? (B2B/B2C, Rollen)", "required": True, "type": "text"},
            {"id": "core_problem", "question": "Welches Problem löst die App?", "required": True, "type": "text"},
            {"id": "mvp_features", "question": "Welche Features sind im MVP? (kommagetrennt)", "required": True, "type": "list"},
            {"id": "nice_to_have", "question": "Welche Features sind Nice-to-Have?", "required": False, "type": "list"},
        ],
    },
    {
        "phase": 2,
        "name": "Datenmodell",
        "questions": [
            {"id": "entities", "question": "Welche Haupt-Entitäten gibt es? (z.B. User, Project, Task)", "required": True, "type": "entities"},
            {"id": "tenant_scoped", "question": "Multi-Tenant? (ja/nein)", "required": True, "type": "boolean"},
            {"id": "soft_delete", "question": "Soft-Delete für welche Entitäten?", "required": False, "type": "list"},
        ],
    },
    {
        "phase": 3,
        "name": "API & Endpunkte",
        "questions": [
            {"id": "crud", "question": "Für welche Entitäten CRUD-Operationen? (alle/auswahl)", "required": True, "type": "list"},
            {"id": "custom_endpoints", "question": "Spezielle Endpunkte? (z.B. /search, /export)", "required": False, "type": "list"},
            {"id": "pagination", "question": "Pagination-Typ? (cursor/offset/none)", "required": True, "type": "choice", "choices": ["cursor", "offset", "none"]},
            {"id": "rate_limit", "question": "Rate Limit (Requests/Minute pro Tenant)?", "required": True, "type": "text"},
        ],
    },
    {
        "phase": 4,
        "name": "Authentifizierung & Autorisierung",
        "questions": [
            {"id": "auth_method", "question": "Auth-Methode? (email_password/oauth_google/oauth_github/magic_link/api_key)", "required": True, "type": "choice", "choices": ["email_password", "oauth_google", "oauth_github", "magic_link", "api_key"]},
            {"id": "roles", "question": "Welche Rollen? (kommagetrennt, default: owner,admin,member,viewer)", "required": True, "type": "list"},
            {"id": "tenant_onboarding", "question": "Tenant-Onboarding? (self_service/admin_provisioned)", "required": True, "type": "choice", "choices": ["self_service", "admin_provisioned"]},
        ],
    },
    {
        "phase": 5,
        "name": "Frontend",
        "questions": [
            {"id": "frontend", "question": "Frontend-Framework? (react/vue/svelte/none)", "required": True, "type": "choice", "choices": ["react", "vue", "svelte", "none"]},
            {"id": "pages", "question": "Welche Seiten/Views? (kommagetrennt)", "required": True, "type": "list"},
            {"id": "responsive", "question": "Responsive? (mobile_first/desktop_first)", "required": True, "type": "choice", "choices": ["mobile_first", "desktop_first"]},
            {"id": "dark_mode", "question": "Dark Mode? (ja/nein)", "required": False, "type": "boolean"},
            {"id": "i18n", "question": "Sprachen? (kommagetrennt, z.B. de,en)", "required": False, "type": "list"},
        ],
    },
    {
        "phase": 6,
        "name": "Integrationen",
        "questions": [
            {"id": "integrations", "question": "Externe Integrationen? (stripe,sendgrid,s3,slack,github)", "required": False, "type": "list"},
            {"id": "webhooks_outbound", "question": "Ausgehende Webhooks? (Events kommagetrennt)", "required": False, "type": "list"},
            {"id": "import_export", "question": "Import/Export? (csv,json,pdf)", "required": False, "type": "list"},
        ],
    },
    {
        "phase": 7,
        "name": "Nicht-funktionale Anforderungen",
        "questions": [
            {"id": "expected_users", "question": "Erwartete Nutzerzahl?", "required": True, "type": "number"},
            {"id": "response_time", "question": "Response-Zeit-Ziel (ms)?", "required": True, "type": "number"},
            {"id": "compliance", "question": "Compliance? (gdpr,hipaa,soc2)", "required": True, "type": "list"},
            {"id": "backup", "question": "Backup-Strategie?", "required": True, "type": "text"},
        ],
    },
]
