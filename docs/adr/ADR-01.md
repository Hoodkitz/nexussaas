# ADR-01: Modularer Backend-Service + Worker

## Status: Accepted

## Kontext
Agenten-Workflows benötigen zustandsbehaftete Orchestrierung mit Interrupts und Wiederaufnahme.

## Entscheidung
Ein modularer Backend-Service plus separater Worker/Orchestrator im MVP.
Agenten als klar abgegrenzte Graph-Nodes. Microservices erst bei konkretem Skalierungs-/Isolationserfordernis.

## Konsequenzen
- Einfachere Entwicklung und Deployment
- Klare Trennung zwischen API und Workflow-Ausführung
- Skalierung durch Worker-Pool
