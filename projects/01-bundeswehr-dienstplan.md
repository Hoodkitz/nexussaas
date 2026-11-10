# Projekt 1: Bundeswehr Dienstplan — Vollautomatisierte Dienstplanung

## Vision
Eine vollautomatisierte Software zur Erstellung, Verwaltung und Optimierung von Dienstplänen für die Bundeswehr. Verkaufbar an das Verteidigungsministerium und Bundeswehr-Einheiten.

## Kernfunktionen
- Automatische Dienstplan-Generierung basierend auf Personalverfügbarkeit, Qualifikationen, Urlaub, Krankheit
- Berücksichtigung von Vorschriften (Arbeitszeitgesetz, Bundeswehr-interne Regelungen)
- Rollen-basierte Zugriffe (Kompaniechef, Zugführer, Soldat)
- Schichtplanung, Wachdienst, Übungsbetrieb
- Export als PDF, Excel, Druck
- Mobile App für Soldaten (Dienstplan einsehen, Tausch anfragen)

## Zielgruppe
Bundeswehr (Kompanien, Bataillone, Einheiten), Verteidigungsministerium

## Technische Anforderungen
- Multi-Tenant (pro Einheit/Kompanie)
- Rollen: Admin, Planer, Soldat (Viewer)
- DSGVO-konform, BSI-Grundschutz
- Offline-fähig (Feldlager)
- Export: PDF, Excel, Kalender (iCal)

## Monetarisierung
- Lizenzmodell pro Einheit
- Enterprise-Lizenz für Bataillone
- Wartungsvertrag

---

# Präzisierung aus der Architekturspezifikation v1.0 (PDF vom 10.11.2026)

Verbindliche Abweichungen gegenüber dem Kurz-Blueprint; MVP-Umsetzung hinter Adaptern, Enterprise-Teile als Fakes/ADR-Notiz.

## Recht & Constraints (Hard = Plan unzulässig, Medium, Soft)
| Constraint | Ebene | Grundlage | Regel |
|---|---|---|---|
| ruhezeitEinhaltung | Hard | § 5 SAZV / § 5 ArbZG | ≥ 11 h zwischen zwei Schichten desselben Soldaten |
| maxTagesarbeitszeit | Hard | § 7 SAZV | ≤ 13 h pro Kalendertag im Grundbetrieb |
| erforderlicheQualifikation | Hard | UZwGBw / Dienstvorschrift | Schicht-ATN muss im Skill-Set liegen |
| keineDoppelbelegung | Hard | logisch | keine überlappenden Schichten je Soldat |
| ausnahmeParagraph30c | Hard-Schalter | § 30c Abs. 4 SG | Einsatz-/Übungs-Flagge deaktiviert Standardgrenzen, aktiviert Sonderregeln |
| bereitschaftsDeckelung | Medium | § 12 SAZV | ≤ 48 h/Woche im Mehrwochen-Mittel (Sanität ≤ 54 h mit Opt-Out, § 13) |
| faireBelastungsverteilung | Soft | Fairness | Varianz Gesamtstunden/Nachtdienste minimieren |
| soldatenWunsch | Soft | Dienstzufriedenheit | Präferenzen belohnen |
Regelarbeitszeit 41 h/Woche (§ 30c SG). Plan nur feasible bei Hard-Score 0. Kein LLM für die Zuweisung.

## Architektur-Entscheidungen (ADR-01..08)
- Solver entkoppelt vom API-Gateway (eigener Service/Modul). Spec nennt Timefold ConstraintStreams; **MVP: CP-SAT (OR-Tools) hinter `SolverPort` ist zulässig**, solange die Constraint-Matrix oben 1:1 als Tests abgebildet ist (ConstraintVerifier-Äquivalent: je Regel ein Test „Konstellation X → Penalty Y“).
- PostgreSQL RLS mit `FORCE ROW LEVEL SECURITY`, App-Rolle ohne BYPASSRLS, `SET LOCAL app.current_tenant_id` pro Transaktion.
- Workflow-Zustände: DRAFT_INIT → DATA_FETCHING → CONSTRAINT_VALIDATION → SOLVER_OPTIMIZING → HARDFEASIBILITY_CHECK → SIMULATION_REVIEW → COMMAND_APPROVAL_INTERRUPT (Kompaniechef, § 10 SG) → PUBLISHED → REALTIME_REPLANNING (Pinning begonnener Schichten). Seiteneffekte (Benachrichtigung, Export) nur in Knoten **nach** der Freigabe; alles davor idempotent. Spec nennt LangGraph + Postgres-Checkpointer; MVP: persistente State-Machine in Postgres reicht, Interrupt/Resume als API.
- Auth: **kein OAuth2 Password Flow** (RFC 9700). OIDC Authorization Code + PKCE; Access-Token 15 min; Refresh-Rotation mit Replay-Erkennung (Wiederverwendung → ganze Session-Familie widerrufen). MVP: Mock-OIDC in compose + Adapter.
- Transactional Outbox für Exporte (DATEV LODAS vs. Lohn und Gehalt unterscheiden: Datumsformat, Dezimaltrenner, Spaltenreihenfolge, Windows-1252).
- Offline/Edge: Read-Only-Kopie (SQLite/IndexedDB), offline nur Verfügbarkeitsmeldung/Tauschgesuch; Re-Sync mit OCC/CRDT, Vorgesetzten-Entscheidung hat Vorrang.
- Löschung Art. 17 DSGVO: keine Soft-Delete-Lösung; Löschkaskade (DB, Cache, Objektspeicher) + Deletion Registry, Crypto-Shredding für Backups (MVP: Registry-Tabelle + Kaskade, Shredding als Adapter-Stub).
- Sandbox für Regelskripte nur gVisor/MicroVM, egress deny, 512 MB / 30 s (MVP: nicht umsetzen, nur Port + Fake).
- Rate-Limiting Redis Token-Bucket (Lua).

## API (Pflicht im MVP)
`POST /api/v1/jobs/roster` (Planer/Admin, Idempotency-Key), `GET /api/v1/jobs/roster/{id}`, `POST .../approve` (Kommandeur, Audit),
`POST .../cancel`, `GET /api/v1/roster/my-shifts` (Soldat), `POST /api/v1/roster/trades`, `POST /api/v1/exports/datev` (Outbox),
`GET /api/v1/users/me/export` (Art. 15), `DELETE /api/v1/users/me` (Art. 17).

## Datenmodell
tenants (Einheit, Klassifizierung), soldat (Dienstgrad, Personalnummer, ATNs, AZK-Referenz), dienstposten_schicht (Soll, ATN, Zeiten, Anrechnungsfaktor),
dienstplan (Zeitraum, Status, approver_id, Audit), arbeitszeitkonto (Stunden, Mehrarbeit, Bereitschaft, Freizeitausgleich § 22/23 SAZV), datev_outbox, deletion_registry, audit_log.

## NFR / Tests
Solver P95 < 30 s für 150 Soldaten × 30 Tage; 0 Cross-Tenant-Treffer in RLS-Tests; Constraint-Tests je Regel; Crash-Recovery des Workflows.
Repo-Struktur (Soll): apps/{api,solver-service,worker,edge-relay}, packages/{domain,constraints,orchestration,security,sandbox,storage}, migrations, tests/{unit,solver,integration,security,e2e}.
