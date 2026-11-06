"""Security scanning adapters (stub)."""
class ScannerAdapter:
    def __init__(self, tool: str):
        self.tool = tool

    def scan(self, artifact_path: str) -> dict:
        # TODO: invoke ruff, bandit, semgrep, dependency scanner
        return {"tool": self.tool, "findings": [], "status": "passed"}

SCANNERS = ["ruff", "bandit", "semgrep"]
