# Projekt 4: Series Sync — Automatische Synchronisation von Serien/Filmen

## Vision
Ein Programm das Serien und Filme automatisch ins Deutsche synchronisiert. Lippenbewegung wird angepasst, Stimmklone werden erstellt, Slang und Stimmcharakteristika werden übertragen. Output ist eine perfekte, fehlerfreie deutsche Synchronisation.

## Kernfunktionen
- **Upload:** Hochladen von Folgen/Episoden
- **Transkription:** Automatische Transkription der Originalsprache
- **Übersetzung:** Übersetzung ins Deutsche mit Beibehaltung von Slang, Wortwitz, kulturellen Referenzen
- **Stimmklon:** Erstellung von Stimmklonen für jeden Charakter (Voice Cloning)
- **Lip-Sync:** Anpassung der Lippenbewegung an die deutsche Synchronisation
- **Stimmcharakteristika:** Übertragung von Stimmmerkmalen (Tonhöhe, Tempo, Emotion)
- **Qualitätsprüfung:** Automatische Prüfung auf Fehler (Lip-Sync, Audio-Qualität, Übersetzungsfehler)
- **Output:** Perfekte, fehlerfreie deutsche Folge

## Zielgruppe
Streaming-Plattformen, Filmstudios, Content-Distributoren, YouTuber

## Technische Anforderungen
- AI Voice Cloning (ElevenLabs, Coqui TTS)
- Lip-Sync AI (Wav2Lip, SadTalker)
- Speech-to-Text (Whisper)
- Machine Translation (DeepL, GPT-4)
- Video Processing (FFmpeg)
- Quality Assurance Pipeline (automatische Fehlererkennung)

## Monetarisierung
- Pay-per-Episode
- Monatliches Abo für Studios
- Enterprise-Lizenz

---

# Präzisierung aus dem Enterprise-Blueprint „Series Sync“ (PDF vom 10.11.2026)

Leitplanke bleibt: Stimmklon nur mit dokumentierter, ausdrücklicher Einwilligung (Art. 9 DSGVO, biometrisch) + Rechtenachweis am Material; Widerruf löst Löschpipeline aus.

## ADRs
- ADR-01 Orchestrierung mit **Temporal** (Durable Execution, deterministische Workflows, Activities mit Heartbeats je Chunk, Retry-Policies: transient = Backoff, permanent = sofort fail). MVP: `WorkflowPort` mit eigener persistenter Job-/Stufen-Maschine in Postgres (Chunk-Fortschritt, Resume nach Crash als Test); Temporal als Adapter später.
- ADR-02/05 Jede FFmpeg-Demux-Stufe für User-Uploads nur in gVisor/Landlock-Sandbox (PixelSmash CVE-2026-8461, CVE-2026-18393); GPU via gVisor nvproxy/CDI. MVP: `SandboxPort` (Fake), Hinweis in README, kein Rohparsing ohne Port.
- ADR-03 **C2PA-Manifest** (c2pa-python, JUMBF, Assertion `c2pa.ai-disclosure`, Aktionen c2pa.edited/created) in jedes Ausgabeartefakt; zusätzlich Soft-Binding-Wasserzeichen (SynthID-Muster). MVP: `ProvenancePort` mit Fake-Signer + Manifest-JSON neben der Datei; echte X.509/HSM später.
- ADR-04 RLS FORCE + `SET LOCAL app.tenant_id`, App-Rolle nie Tabellen-Owner, kein BYPASSRLS.
- ADR-06 Lip-Sync: Wav2Lip + CodeFormer (nicht GFPGAN) hinter Adapter; ADR-07 Time-Stretch per **WSOLA** (Rubberband in FFmpeg), kein Resampling; ADR-08 Löschung = Kaskade DB/Cache/S3 + Deletion Registry, kein Soft-Delete.

## Pipeline-Stufen (je Stufe ein Adapter + Fake)
1. Ingest (Sandbox) → 2. Stem-Separation HTDemucs `--two-stems=vocals` (GPU) → 3. Diarization pyannote 3.1 → 4. ASR + Forced Alignment WhisperX (±50 ms Wortzeitstempel, Silero VAD)
→ 5. Übersetzung (LLM, Slang/Kontext) → 6. Voice-Clone/TTS je Sprecher-ID (nur mit Consent-Record) → 7. WSOLA-Fit in Zeitfenster → 8. Wav2Lip + CodeFormer
→ 9. QA-Gate SyncNet: LSE-D ≤ 9.5, LSE-C ≥ 4.5, sonst Retry mit anderen Parametern oder HITL-Eskalation → 10. Mastering: Dialog -27 LKFS ±2, True Peak -2 dBTP (Netflix) → 11. C2PA-Injektion + Auslieferung.

## Auth / NFR
OIDC Authorization Code + PKCE (kein Password Flow). API P95 < 500 ms, Jobannahme < 2 s; SIGKILL eines Workers → Resume ab letztem Chunk; Stripe-Webhooks idempotent; keine Secrets/Biometrie in Logs, Trace-IDs pseudonym.
Repo-Soll: apps/{api,orchestrator,workers}, packages/{database,media_processing,ml_pipeline,security_c2pa,qa_metrics}, infrastructure/{temporal_cluster,sandbox_gvisor}, tests/{unit,integration,security,e2e}, docs/.
