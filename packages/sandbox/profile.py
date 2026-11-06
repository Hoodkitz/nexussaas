"""Sandbox hardened profile configuration."""
SANDBOX_PROFILE = {
    "user": "nobody",
    "read_only_root": True,
    "drop_capabilities": ["ALL"],
    "no_new_privileges": True,
    "seccomp": "default",
    "apparmor": "docker-default",
    "network": "none",
    "cpu_limit": "1.0",
    "memory_limit": "512m",
    "pids_limit": 256,
    "timeout_seconds": 300,
    "output_limit_mb": 10,
    "tmpfs_size": "100m",
    "env": {},
}
