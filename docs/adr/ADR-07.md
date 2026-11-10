# ADR-07: Art. 17 Löschung ≠ Soft-Delete

## Status: Accepted

## Kontext
DSGVO Art. 17 (Recht auf Löschung) erfordert echte Löschung/Anonymisierung.

## Entscheidung
Soft-Delete ist nur Status-/Workflowhilfe. Löschpipeline muss aktive DB, Object Storage,
Search/Cache, Logs, Checkpoints, Queue, Drittanbieter und Backups betrachten.
Gesetzliche Aufbewahrung und Art.-17-Ausnahmen dokumentieren.

## Konsequenzen
- Deletion Registry beim Restore anwenden
- Backups "beyond use" halten
- Crypto-Shredding als Option bewerten

## Implementierung (v0.2)
`DELETE /api/v1/users/me` löscht hart (siehe docs/runbooks/data-deletion.md).
