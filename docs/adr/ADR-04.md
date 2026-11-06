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
