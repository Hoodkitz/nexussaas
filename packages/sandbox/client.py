"""Sandbox runner client (stub)."""
import subprocess
import json

class SandboxClient:
    def __init__(self, runner_url: str = "http://localhost:9000"):
        self.runner_url = runner_url

    def run(self, artifact_bundle: dict, timeout: int = 300) -> dict:
        """Execute untrusted code in sandbox. Returns structured result."""
        # TODO: POST to sandbox runner, receive logs + test results
        return {
            "status": "passed",
            "exit_code": 0,
            "logs": "",
            "duration_ms": 0,
        }

    def health(self) -> bool:
        return True
