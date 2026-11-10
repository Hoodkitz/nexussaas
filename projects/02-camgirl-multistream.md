# Projekt 2: CamGirl Multi-Stream — Multi-Portal Streaming + Chat-Bündelung

## Vision
Eine App für Erotikmodels/Camgirls, die gleichzeitig an alle Cam-Portale streamt und alle Chats in einer einzigen App bündelt.

## Kernfunktionen
- **Multi-Stream:** Eine Webcam → gleichzeitig an alle Portale (Chaturbate, Stripchat, MyFreeCams, etc.)
- **Chat-Bündelung:** Handy-App mit Reitern, pro Reiter ein Chat-Fenster eines Portals
- **Schnellwechsel:** Durch Klicken zwischen Chat-Fenstern wechseln
- **Benachrichtigungen:** Push-Notifications bei neuen Nachrichten in jedem Portal
- **Statistiken:** Einnahmen, Zuschauer, Chat-Aktivität pro Portal
- **Automatische Begrüßung:** Vorgefertigte Nachrichten für neue Zuschauer

## Zielgruppe
Camgirls, Erotikmodels, Content Creator

## Technische Anforderungen
- RTMP/SRT Streaming zu mehreren Endpunkten
- WebSocket-basierte Chat-Integration pro Portal
- Mobile App (React Native / Flutter)
- Push-Notifications
- Verschlüsselte Speicherung von Credentials

## Monetarisierung
- Monatliches Abo
- Provision pro verdientem Betrag (optional)
- Premium-Features (Auto-Responder, Statistiken)

---

# Präzisierung aus der Architekturspezifikation (PDF vom 10.11.2026)

Leitplanken bleiben: nur offizielle Portal-Schnittstellen (RTMP-Ingest-URL + Stream-Key, offizielle Chat-APIs/Webhooks), kein Scraping, keine Umgehung von Portalregeln.

## ADRs
- ADR-01 Ingest/Fan-out-Engine: **SRS** (RTMP 1935 / SRT 6000), transkodierungsfreier RTMP-Re-Push, `on_publish`-HTTP-Callback an die API (`POST /api/v1/streams/verify`, Shared Secret + IP-Allowlist) liefert Ziel-URIs. MVP: ffmpeg-Fan-out-Worker hinter `RestreamPort` ist zulässig; SRS als zweiter Adapter/compose-Service, Callback-Endpunkt muss existieren.
- ADR-02 Stateful WebSocket-Gateways getrennt von stateless API; Redis Pub/Sub-Backplane; Heartbeat 30 s / Pong-Timeout 10 s; Graceful Drain (gestaffelte Reconnects, kein Thundering Herd).
- ADR-03 Inbound-Chat-Event-Bus: **Redis Streams** `stream:chat:{tenant_id}` (XADD, Consumer Groups, XREVRANGE für Reconnect-Nachladen).
- ADR-04 Credentials: Envelope Encryption AES-256-GCM, DEK pro Datensatz, KEK im KMS/HSM, AAD = tenant_id + platform_id. Spalten: encrypted_credentials, wrapped_dek, iv, auth_tag, kek_version. MVP: `KmsPort` mit lokalem Fake-KEK aus Env; Fernet ist nur Übergang.
- ADR-05 RLS mit FORCE, `SET LOCAL app.tenant_id`, App-Rolle ohne BYPASSRLS; Query ohne Kontext → leere Menge (Test!).
- ADR-06 Transactional Outbox (`transactional_outbox`, FOR UPDATE SKIP LOCKED, Backoff+Jitter) für externe Effekte (OBS-Webhooks bei Spendenziel).
- ADR-07 Idempotente Inbox für Webhooks (`webhook_inbox`, UNIQUE event_id, HMAC prüfen, 200 bei Duplikat).
- ADR-08 Crypto-Shredding (KEK löschen) für Art. 17; MVP: Deletion-Registry + Kaskade, Shredding über KmsPort.

## Normalisiertes Chat-Event (JSON)
event_id, tenant_id, stream_id, platform, event_type (message|tip|...), timestamp, sender{platform_user_id, username, badge_level},
payload{message, tokens_spent, fiat_equivalent_usd, is_private_request}.

## Auth/API
OAuth2 Authorization Code + PKCE (kein Password Grant), Access 15 min, Refresh-Rotation mit Replay-Erkennung, DPoP optional.
Endpunkte: POST /api/v1/auth/token, POST /api/v1/streams/verify, GET /api/v1/streams/targets, POST /api/v1/credentials, WS /ws/v1/chat (Ticket-Token),
POST /api/v1/outbox/trigger (HMAC), POST /api/v1/webhooks/stripe, DELETE /api/v1/tenants/me (Re-Auth, Shredding).

## Quotas / Limits
REST 60 req/min/User; Connector 1000 Events/min/Kanal; WS 500 msg/s/Verbindung; 429 + Retry-After. Standard-Tarif: 1 Ingest, 3 Ziele; Agentur: 3 Ingest; Pro: 10 Ziele. Wall-Time-Cap 24 h je Stream.
Retention: Chat-Logs 30 Tage physisch löschen; Umsatz-/Tipp-Logs 10 Jahre (spaltenverschlüsselt); Credentials sofort bei Trennung; flüchtige Zustände ≤ 60 s.

## NFR
API P95 < 200 ms; Chat-Zustellung P99 < 100 ms; Fan-out-Latenz +< 200 ms; 50k WSS/Knoten (später, Go/Rust-Gateway); RPO < 1 min, RTO < 15 min.
Repo-Soll: apps/{api,websocket-gateway,chat-connectors,outbox-worker}, packages/{common-domain,crypto-vault,schema-normalizer,storage}, migrations, tests/{unit,integration,load}.
