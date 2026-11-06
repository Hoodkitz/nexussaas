# NexusSaaS Blueprint Template v1.0

## Zweck
Diese Vorlage definiert die Struktur für einen vollständigen App-Blueprint, den NexusSaaS nach Abschluss der Anforderungserfassung erzeugt. Die KI fragt Schritt für Schritt ab und füllt diesen Blueprint aus.

## Abfrage-Reihenfolge (KI fragt in dieser Reihenfolge)

### Phase 1: Vision & Scope
1. **App-Name** (Pflicht): Wie heißt die Anwendung?
2. **Kurzbeschreibung** (Pflicht): In einem Satz — was macht die App?
3. **Zielgruppe** (Pflicht): Wer nutzt die App? (B2B/B2C, Rollen, Persona)
4. **Kernproblem** (Pflicht): Welches Problem löst die App?
5. **MVP-Scope** (Pflicht): Welche Features sind im MVP? (Must-Have vs. Nice-to-Have)

### Phase 2: Datenmodell
6. **Entitäten** (Pflicht): Welche Hauptobjekte gibt es? (z.B. User, Project, Task)
   - Für jede Entität: Felder, Datentypen, Beziehungen (1:1, 1:n, n:m)
   - Pflichtfelder vs. optionale Felder
   - Validierungsregeln (min/max, Regex, Enum-Werte)
7. **Tenant-Isolation** (Pflicht): Multi-Tenant? Welche Daten sind tenant-scoped?
8. **Soft-Delete** (Optional): Welche Entitäten unterstützen Soft-Delete?

### Phase 3: API & Endpunkte
9. **CRUD-Operationen** (Pflicht): Für jede Entität — welche CRUD-Operationen?
10. **Custom Endpoints** (Optional): Spezielle Endpunkte (z.B. /search, /export, /bulk)
11. **Pagination** (Pflicht): Cursor-basiert oder Offset? Default-Limit?
12. **Filtering/Sorting** (Optional): Welche Felder filterbar/sortierbar?
13. **Rate Limiting** (Pflicht): Requests pro Minute pro Tenant?

### Phase 4: Authentifizierung & Autorisierung
14. **Auth-Methode** (Pflicht): Email/Passwort, OAuth (Google/GitHub), Magic Link, API Key?
15. **Rollen** (Pflicht): Welche Rollen gibt es? (Owner, Admin, Member, Viewer)
16. **Permissions** (Pflicht): Welche Aktionen pro Rolle? (CRUD-Matrix)
17. **Tenant-Onboarding** (Pflicht): Self-Service oder Admin-provisioned?

### Phase 5: Frontend
18. **Framework** (Pflicht): React, Vue, Svelte, oder nur API?
19. **Seiten/Views** (Pflicht): Welche Seiten gibt es? (Dashboard, List, Detail, Form)
20. **Responsive** (Pflicht): Mobile-first oder Desktop-first?
21. **Dark Mode** (Optional): Unterstützt?
22. **i18n** (Optional): Mehrsprachig? Welche Sprachen?

### Phase 6: Integrationen
23. **Externe APIs** (Optional): Welche Drittanbieter-Integrationen? (Stripe, SendGrid, S3)
24. **Webhooks** (Optional): Ausgehende Webhooks? Welche Events?
25. **Import/Export** (Optional): CSV, JSON, PDF Export?

### Phase 7: Nicht-funktionale Anforderungen
26. **Performance** (Pflicht): Erwartete Nutzerzahl, Response-Zeit-Ziel
27. **SLA** (Optional): Uptime-Anforderung
28. **Compliance** (Pflicht): DSGVO, HIPAA, SOC2?
29. **Backup** (Pflicht): Backup-Strategie
30. **Monitoring** (Pflicht): Welche Metriken/Alerts?

---

## Blueprint Output Format (JSON)

Nach Abschluss aller Phasen erzeugt NexusSaaS folgenden Blueprint:

```json
{
  "name": "string",
  "version": "1.0",
  "description": "string",
  "target_audience": "string",
  "core_problem": "string",
  "mvp_features": ["string"],
  "nice_to_have": ["string"],
  "entities": [
    {
      "name": "string",
      "fields": [
        {"name": "string", "type": "uuid|text|integer|boolean|timestamp|jsonb|enum", "required": true, "unique": false, "default": null, "validation": "string"}
      ],
      "relationships": [
        {"type": "1:1|1:n|n:m", "target": "string", "foreign_key": "string"}
      ],
      "soft_delete": false,
      "tenant_scoped": true
    }
  ],
  "endpoints": [
    {
      "method": "GET|POST|PUT|PATCH|DELETE",
      "path": "string",
      "description": "string",
      "auth_required": true,
      "roles": ["owner", "admin", "member", "viewer"],
      "request_body": "schema_ref",
      "response_body": "schema_ref",
      "pagination": "cursor|offset|none",
      "rate_limit": "string"
    }
  ],
  "auth": {
    "method": "email_password|oauth_google|oauth_github|magic_link|api_key",
    "roles": ["owner", "admin", "member", "viewer"],
    "permissions": {
      "owner": ["read", "write", "delete", "admin", "billing"],
      "admin": ["read", "write", "delete", "admin"],
      "member": ["read", "write"],
      "viewer": ["read"]
    },
    "tenant_onboarding": "self_service|admin_provisioned"
  },
  "frontend": {
    "framework": "react|vue|svelte|none",
    "pages": [
      {"name": "string", "path": "string", "description": "string", "auth_required": true}
    ],
    "responsive": "mobile_first|desktop_first",
    "dark_mode": false,
    "i18n": ["de", "en"]
  },
  "integrations": [
    {
      "provider": "stripe|sendgrid|s3|slack|github",
      "purpose": "string",
      "config_keys": ["string"]
    }
  ],
  "webhooks_outbound": [
    {"event": "string", "payload": "schema_ref", "retry_policy": "string"}
  ],
  "non_functional": {
    "expected_users": "number",
    "response_time_ms": "number",
    "uptime_sla": "string",
    "compliance": ["gdpr", "hipaa", "soc2"],
    "backup_strategy": "string",
    "monitoring": ["metrics", "alerts", "logging"]
  }
}
```

## Abfrage-Protokoll (KI-Verhalten)

1. **Eine Frage pro Runde** — nicht alle auf einmal
2. **Pflichtfelder zuerst** — erst wenn alle Pflichtfelder beantwortet sind, optionale abfragen
3. **Validierung** — jede Antwort validieren (z.B. App-Name nicht leer, Entitäten mindestens 1)
4. **Zusammenfassung** — nach jeder Phase eine Zusammenfassung der bisherigen Antworten
5. **Rückfragen** — bei unklaren Antworten nachfragen, nicht raten
6. **Blueprint-Generierung** — erst nach Abschluss aller Phasen den Blueprint erzeugen
7. **Review** — Blueprint dem User zur Freigabe vorlegen, bevor App-Erstellung startet

## Beispiel-Dialog

```
KI: Wie soll die App heißen?
User: TaskFlow
KI: Kurzbeschreibung in einem Satz?
User: Ein Task-Management-Tool für kleine Teams
KI: Wer nutzt die App? (B2B/B2C, Rollen)
User: B2B, Teams mit 2-20 Personen
KI: Welches Problem löst die App?
User: Aufgaben gehen in E-Mails und Chats verloren
KI: Welche Features sind im MVP?
User: Tasks erstellen, zuweisen, Status ändern, Kommentare, Benachrichtigungen
...
```
