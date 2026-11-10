"""Static checks and security scanning for generated artifacts.

These tools only parse code (ast/ruff/bandit); nothing generated is executed here.
Execution happens exclusively in the sandbox.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "stripe_secret": re.compile(r"sk_(?:live|test)_[0-9A-Za-z]{16,}"),
    "generic_secret": re.compile(r"(?i)(?:password|secret|api_key)\s*=\s*['\"][^'\"]{8,}['\"]"),
}


def _write(files: dict[str, str], root: Path) -> None:
    for rel, content in files.items():
        p = (root / rel).resolve()
        if root.resolve() not in p.parents:
            raise ValueError(f"path escapes root: {rel}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def syntax_check(files: dict[str, str]) -> list[dict]:
    findings = []
    for rel, content in sorted(files.items()):
        if rel.endswith(".py"):
            try:
                ast.parse(content, filename=rel)
            except SyntaxError as e:
                findings.append({"tool": "ast", "severity": "high", "file": rel, "line": e.lineno, "msg": e.msg})
    return findings


def ruff_check(root: Path) -> list[dict]:
    r = subprocess.run([sys.executable, "-m", "ruff", "check", "--no-cache", "--output-format", "json",
                        "--select", "E,F,B", "--ignore", "E501,B008", "--target-version", "py311", str(root)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode not in (0, 1):
        return [{"tool": "ruff", "severity": "high", "msg": f"ruff failed: {r.stderr[-300:]}"}]
    return [{"tool": "ruff", "severity": "medium", "file": str(Path(i["filename"]).relative_to(root)),
             "line": i["location"]["row"], "code": i["code"], "msg": i["message"]}
            for i in json.loads(r.stdout or "[]")]


def bandit_check(root: Path) -> list[dict]:
    r = subprocess.run([sys.executable, "-m", "bandit", "-q", "-r", "-f", "json", "--exclude", str(root / "tests"),
                        str(root)], capture_output=True, text=True, timeout=180)
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return [{"tool": "bandit", "severity": "high", "msg": f"bandit failed: {r.stderr[-300:]}"}]
    return [{"tool": "bandit", "severity": i["issue_severity"].lower(), "file": str(Path(i["filename"]).relative_to(root)),
             "line": i["line_number"], "code": i["test_id"], "msg": i["issue_text"]}
            for i in data.get("results", [])]


def secret_scan(files: dict[str, str]) -> list[dict]:
    out = []
    for rel, content in sorted(files.items()):
        for name, pat in SECRET_PATTERNS.items():
            for m in pat.finditer(content):
                out.append({"tool": "secrets", "severity": "high", "file": rel,
                            "line": content[:m.start()].count("\n") + 1, "code": name, "msg": "possible secret"})
    return out


def ddl_policy_check(files: dict[str, str], tables: list[str]) -> list[dict]:
    ddl = files.get("migrations/001_init.sql", "")
    out = []
    for t in tables:
        for needle in (f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY', f'ALTER TABLE "{t}" FORCE ROW LEVEL SECURITY',
                       f'CREATE POLICY tenant_isolation ON "{t}"'):
            if needle not in ddl:
                out.append({"tool": "rls", "severity": "high", "file": "migrations/001_init.sql",
                            "msg": f"missing: {needle}"})
    return out


def static_checks(files: dict[str, str]) -> dict:
    findings = syntax_check(files)
    with tempfile.TemporaryDirectory(prefix="nexus-static-") as d:
        root = Path(d)
        _write(files, root)
        if not findings:
            findings += ruff_check(root)
    return {"passed": not any(f["severity"] == "high" for f in findings) and not findings, "findings": findings}


def security_review(files: dict[str, str], tables: list[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="nexus-sec-") as d:
        root = Path(d)
        _write(files, root)
        findings = bandit_check(root)
    findings += secret_scan(files) + ddl_policy_check(files, tables)
    blocking = [f for f in findings if f["severity"] == "high"]
    return {"passed": not blocking, "blocking": len(blocking), "findings": findings}
