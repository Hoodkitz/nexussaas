# Projekt 3: Fan Chat AI — Automatisierte Chat-Betreuung für Erotikmodels

## Vision
Eine KI die im Namen von Amateur-Erotikmodels die Fan-Chats auf allen Portalen betreut. Lernt den Schreibstil des Models, sammelt Fan-Informationen und pflegt Kontakte autonom.

## Kernfunktionen
- **Chat-Analyse:** Liest bisherige Chats und lernt den Schreibstil des Models
- **Fan-Datenbank:** Pro Fan eine separate Datenbank mit Infos (Name, Vorlieben, Kaufhistorie, letzter Kontakt)
- **Model-Datenbank:** Infos über das Model (Persönlichkeit, Vorlieben, Grenzen, Preise)
- **Automatische Antworten:** Antwortet stellvertretend im Namen des Models
- **Proaktive Kontaktpflege:** Schreibt Fans in regelmäßigen Abständen an (Geburtstag, neue Content, etc.)
- **Eskalation:** Leitet komplexe/wichtige Chats an das Model weiter
- **Tonalität:** Passt sich dem Schreibstil des Models an (Slang, Emojis, Formalität)

## Zielgruppe
Amateur-Erotikmodels, Content Creator, Agenturen

## Technische Anforderungen
- LLM-basierte Chat-Automation (Claude/GPT)
- RAG (Retrieval Augmented Generation) mit Fan- und Model-Daten
- WebSocket-Integration mit Portal-Chats
- Verschlüsselte Datenbank (DSGVO)
- Dashboard für das Model (Übersicht, Eskalationen, Statistiken)

## Monetarisierung
- Monatliches Abo pro Model
- Enterprise für Agenturen (mehrere Models)

---

# Präzisierung aus der Architekturspezifikation „CommunityBot“ (PDF vom 10.11.2026)

Leitplanke bleibt: Assistenz, Freigabe durch die Creatorin, sichtbare KI-Kennzeichnung (Art. 50 AI Act). Die Spec beschreibt „stellvertretendes Agieren“; umgesetzt wird es als Entwurf + Freigabe (optional: Auto-Send-Whitelist je Fan nach ausdrücklicher Einstellung der Creatorin, nie Standard).

## ADRs
- RLS in PostgreSQL mit FORCE + `SET LOCAL app.tenant_id` (bereits umgesetzt); **keine separate Vektor-DB**: Retrieval komplett in Postgres.
- Hybrides Retrieval: pgvector (halfvec, HNSW) + tsvector/BM25, Fusion per **Reciprocal Rank Fusion** (k=60, je Zweig 20–50 Kandidaten) in einer SQL-Query (FULL OUTER JOIN über zwei CTEs); danach Cross-Encoder-Reranking (bge-reranker-v2-m3, max 50 Kandidaten) hinter `RerankerPort` (Fake im Test). Filtered-Recall-Collapse beachten: partielle Indizes/iterative Scans je Tenant.
- Zustand/Workflow: LangGraph mit AsyncPostgresSaver + AsyncConnectionPool; AgentState als Pydantic mit Defaults (Schema-Evolution); Checkpoint-GC nach 30 Tagen; Seiteneffekte nur nach dem Interrupt (Freigabe-Node). MVP: bestehende Draft→Decision→Send-Pipeline erfüllt das; LangGraph optional.
- Event-Idempotenz: Redis `SET NX` Lease (15 s) je Event-ID für Webhooks/Retries (Telegram/Discord/Slack wiederholen).
- Plattformen: Discord Hybrid Sharding (ab 2.500 Guilds), MESSAGE_CONTENT-Intent, 120 Events/60 s; Telegram **Local Bot API** (Docker `--local`, 2 GB). Alles als offizielle APIs, Adapter + Fake.
- Langzeitgedächtnis (Mem0/Zep-Muster): asynchrone Fakten-Extraktion („Geburtstag 12. Mai“, „mag X nicht“) als Embeddings im Tenant-Namespace; Dynamic Context Pruning statt ganzer Historie.
- LLM-Sicherheit: Input-/Output-Guardrails (NeMo-Guardrails-Muster, Llama-Guard-Klasse) gegen Indirect Prompt Injection aus Nutzernamen/Profiltexten/RAG; untrusted Segmente markieren. Inferenz: vLLM FP8, Concurrency-Cap (≈64 auf A10) über Redis-Queue. MVP: `GuardrailPort` mit regelbasiertem Fake (Muster „ignore previous“, Link-/Freebie-Forderungen).
- PII-Redaktion (Presidio-Muster) **vor** dem Embedding: Namen, Telefonnummern, Kartendaten → `<EMAIL>`-Platzhalter; Cache für unveränderte Texte.
- Löschung Art. 17: Event → relationale Kaskade → Embedding-Tombstones + Index-Rebuild → Checkpoints der thread_id löschen.

## NFR
API P95 < 200 ms (Webhook-Timeouts), Vektorsuche P95 < 50 ms, Reranking P95 < 800 ms, 0 Cross-Tenant-Treffer (Canary-Tests ohne Tenant-Kontext).
