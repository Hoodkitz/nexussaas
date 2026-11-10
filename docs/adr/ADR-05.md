# ADR-05: PostgreSQL RLS als Defense-in-Depth

## Status: Accepted

## Kontext
Multi-Tenancy erfordert Datenisolation auf DB-Ebene.

## Entscheidung
PostgreSQL RLS ergänzt Applikationsautorisierung. Tenant-ID in tenantbezogenen Tabellen.
RLS mit Default-Deny; FORCE ROW LEVEL SECURITY. Anwendungsrolle kein Tabellenowner.

## Konsequenzen
- Defense-in-Depth, kein Ersatz für API-Autorisierung
- Connection-Pool-Reuse muss getestet werden
- Backup-Prozesse müssen RLS berücksichtigen

## Implementierung (v0.2)
Rolle `nexus_app` ohne SUPERUSER/BYPASSRLS; FORCE RLS auf allen Tenant-Tabellen; Kontext per
`set_config(..., true)` je Transaktion; leerer Kontext = keine Zeilen. Zwei eng begrenzte SECURITY-DEFINER-Funktionen
(`system_stale_jobs`, `system_tenant_for_customer`).
