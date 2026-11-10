# ADR-04: Sandbox-Isolation für untrusted Code

## Status: Accepted

## Kontext
Generierter Code ist untrusted. Standard-Container teilen Host-Kernel.

## Entscheidung
Mindestens gehärteter rootless Runner; für öffentliche/high-risk Ausführung gVisor oder MicroVM.
Keine Docker-Socket-Mounts. Netzwerk standardmäßig deaktiviert.

## Konsequenzen
- Separate host/account/network boundary
- Rootless, read-only root, drop capabilities, seccomp/AppArmor
- CPU/RAM/PID/IO limits, harte Laufzeit- und Output-Limits

## Implementierung (v0.2)
`packages/sandbox/client.py`: `--network none`, `--read-only`, Code read-only gemountet, `--cap-drop ALL`,
`no-new-privileges`, UID 10001, CPU/RAM/PID/ulimits, noexec-tmpfs, Timeout, Output-Limit. gVisor über
`SANDBOX_RUNTIME=runsc`. Offen: separater Runner-Host und gVisor im Betrieb.
