# ADR-03: Große Artefakte in Object Storage

## Status: Accepted

## Kontext
Graph-State sollte klein bleiben; große Artefakte (Code, Logs, Reports) nicht in Checkpoints.

## Entscheidung
State speichert IDs/URIs/Hashes; Artefakte in Object Storage mit content hash, tenant scope, version, retention.

## Konsequenzen
- Kleinere Checkpoint-Payloads
- Trennung von Artefakt-Lifecycle und Workflow
- Restore-Pfade müssen getestet werden
