# ADR-02: LangGraph für zustandsbehaftete Agentenabläufe

## Status: Accepted

## Kontext
Agenten-Workflows mit Interrupts und Wiederaufnahme benötigen persistenten State.

## Entscheidung
LangGraph für zustandsbehaftete Agentenabläufe; PostgreSQL als Checkpointer.
Interrupts und Wiederaufnahme brauchen Checkpointer und stabile thread_id.

## Konsequenzen
- Durable workflow state in PostgreSQL
- Resume semantics mit stabiler thread_id
- Seiteneffekte vor Interrupts müssen idempotent sein

## Implementierung (v0.2)
`packages/orchestration/graph.py`, Checkpointer `PostgresSaver`, `thread_id = job_id`. Freigaben über
`interrupt()`; Entscheidungen sind an die Stufe gebunden. Nodes sind idempotent, Absturz -> Fortsetzung am letzten Checkpoint.
