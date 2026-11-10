"""Sandbox runner: executes untrusted generated code in a locked-down container.

Boundary (ADR-04): no network, read-only root and read-only code mount, all
capabilities dropped, no-new-privileges, unprivileged UID, CPU/memory/PID/file
limits, wall-clock timeout, truncated output. The Docker socket is never mounted
into the sandbox. If ``SANDBOX_RUNTIME=runsc`` is set, gVisor is used as runtime.
Production should run this on a separate host (see docs/adr/ADR-04.md).
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from packages.observability.metrics import SANDBOX_RUNS
from packages.sandbox.profile import SANDBOX_PROFILE as P
from packages.settings import settings


class SandboxUnavailable(RuntimeError):
    pass


class SandboxClient:
    def __init__(self, image: str | None = None, runtime: str | None = None, timeout: int | None = None):
        self.image = image or settings.SANDBOX_IMAGE
        self.runtime = settings.SANDBOX_RUNTIME if runtime is None else runtime
        self.timeout = timeout or settings.SANDBOX_TIMEOUT

    def health(self) -> bool:
        if not shutil.which("docker"):
            return False
        r = subprocess.run(["docker", "image", "inspect", self.image], capture_output=True, timeout=20)
        return r.returncode == 0

    def _cmd(self, name: str, workdir: Path, command: list[str]) -> list[str]:
        cmd = [
            "docker", "run", "--rm", "--name", name,
            "--network", P["network"],
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", P["user"],
            "--cpus", P["cpus"],
            "--memory", P["memory"], "--memory-swap", P["memory"],
            "--pids-limit", str(P["pids_limit"]),
            "--tmpfs", P["tmpfs"],
            "--ipc", "none",
            "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={workdir},target=/work,readonly",
            "--workdir", "/work",
        ]
        for u in P["ulimits"]:
            cmd += ["--ulimit", u]
        if self.runtime:
            cmd += ["--runtime", self.runtime]
        return cmd + [self.image] + command

    def run_files(self, files: dict[str, str], command: list[str]) -> dict:
        """Write files to a fresh temp dir, run ``command`` in the sandbox, return a result dict."""
        if not self.health():
            raise SandboxUnavailable(f"sandbox image {self.image} not available")
        base = Path(settings.SANDBOX_WORKDIR)
        base.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix="run-", dir=base))
        try:
            for rel, content in files.items():
                target = (workdir / rel).resolve()
                if workdir not in target.parents:
                    raise ValueError(f"path escapes workdir: {rel}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            workdir.chmod(0o755)
            for p in workdir.rglob("*"):
                p.chmod(0o755 if p.is_dir() else 0o644)
            return self._execute(workdir, command)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _execute(self, workdir: Path, command: list[str]) -> dict:
        name = f"nexus-sbx-{uuid.uuid4().hex[:12]}"
        start = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(self._cmd(name, workdir, command), capture_output=True, timeout=self.timeout)
            code, out, err = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as e:
            timed_out = True
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=30)
            code, out, err = 124, e.stdout or b"", e.stderr or b""
        limit = P["output_limit_bytes"]
        result = {
            "status": "passed" if code == 0 else ("timeout" if timed_out else "failed"),
            "exit_code": code,
            "stdout": out[-limit:].decode("utf-8", "replace"),
            "stderr": err[-limit:].decode("utf-8", "replace"),
            "duration_ms": int((time.monotonic() - start) * 1000),
            "timed_out": timed_out,
            "runtime": self.runtime or "runc",
            "profile": {k: P[k] for k in ("network", "user", "memory", "pids_limit", "read_only_root")},
        }
        SANDBOX_RUNS.labels(result["status"]).inc()
        return result

    def run_tests(self, files: dict[str, str]) -> dict:
        return self.run_files(files, ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"])
