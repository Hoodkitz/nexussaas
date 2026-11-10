"""Hardened sandbox profile (ADR-04). Applied to every untrusted execution."""
SANDBOX_PROFILE = {
    "user": "10001:10001",
    "read_only_root": True,
    "drop_capabilities": ["ALL"],
    "no_new_privileges": True,
    "network": "none",
    "cpus": "1.0",
    "memory": "512m",
    "pids_limit": 128,
    "tmpfs": "/tmp:rw,noexec,nosuid,nodev,size=64m",
    "ulimits": ["nofile=256:256", "fsize=52428800:52428800"],
    "output_limit_bytes": 1_000_000,
}
