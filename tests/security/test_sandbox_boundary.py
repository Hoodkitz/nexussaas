"""Phase 5 acceptance: sandbox boundary tests (run real containers)."""
import pytest

from packages.sandbox.client import SandboxClient

sbx = SandboxClient(timeout=20)
pytestmark = pytest.mark.skipif(not sbx.health(), reason="sandbox image not built (make sandbox-image)")


def run(code: str) -> dict:
    return sbx.run_files({"probe.py": code}, ["python", "probe.py"])


def test_no_network():
    r = run("import socket\ns=socket.socket(); s.settimeout(3)\n"
            "try:\n    s.connect(('1.1.1.1', 80)); print('CONNECTED')\nexcept OSError as e:\n    print('BLOCKED', e)\n")
    assert "BLOCKED" in r["stdout"] and "CONNECTED" not in r["stdout"]


def test_no_dns():
    r = run("import socket\ntry:\n    socket.gethostbyname('example.com'); print('RESOLVED')\n"
            "except OSError:\n    print('NODNS')\n")
    assert "NODNS" in r["stdout"]


def test_runs_as_unprivileged_user():
    r = run("import os; print(os.getuid(), os.getgid())")
    assert r["stdout"].strip() == "10001 10001"


def test_root_filesystem_and_code_are_read_only():
    r = run("import os\nfor p in ['/etc/x', '/work/x', '/usr/x']:\n"
            "    try:\n        open(p, 'w').write('x'); print('WROTE', p)\n"
            "    except OSError:\n        print('RO', p)\n")
    assert r["stdout"].count("RO") == 3 and "WROTE" not in r["stdout"]


def test_tmp_is_writable_but_noexec():
    r = run("import os, subprocess\nopen('/tmp/a.sh','w').write('#!/bin/sh\\necho hi')\nos.chmod('/tmp/a.sh', 0o755)\n"
            "try:\n    subprocess.run(['/tmp/a.sh'], check=True); print('EXEC')\n"
            "except Exception:\n    print('NOEXEC')\n")
    assert "NOEXEC" in r["stdout"]


def test_capabilities_dropped():
    r = run("print(open('/proc/self/status').read())")
    eff = [ln for ln in r["stdout"].splitlines() if ln.startswith("CapEff")][0]
    assert eff.split()[1] == "0000000000000000"
    nnp = [ln for ln in r["stdout"].splitlines() if ln.startswith("NoNewPrivs")][0]
    assert nnp.split()[1] == "1"


def test_timeout_kills_process():
    quick = SandboxClient(timeout=5)
    r = quick.run_files({"p.py": "import time\ntime.sleep(60)"}, ["python", "p.py"])
    assert r["status"] == "timeout" and r["timed_out"]


def test_memory_limit():
    r = run("x = bytearray(1024 * 1024 * 1024)\nprint('ALLOCATED')")
    assert "ALLOCATED" not in r["stdout"] and r["exit_code"] != 0


def test_pid_limit_stops_fork_bomb():
    r = run("import os, sys\nn=0\ntry:\n    for _ in range(1000):\n        if os.fork() == 0:\n"
            "            import time; time.sleep(5); os._exit(0)\n        n += 1\nexcept OSError:\n    pass\n"
            "print('FORKS', n)\nsys.stdout.flush()\nos._exit(0)\n")
    forks = int(r["stdout"].split("FORKS")[1].split()[0])
    assert forks < 200


def test_no_docker_socket_or_host_paths():
    r = run("import os\nprint(os.path.exists('/var/run/docker.sock'), os.path.exists('/home/administrator'))")
    assert r["stdout"].strip() == "False False"


def test_output_is_truncated():
    r = run("print('x' * 3_000_000)")
    assert len(r["stdout"]) <= 1_000_000


def test_path_traversal_in_files_rejected():
    with pytest.raises(ValueError):
        sbx.run_files({"../escape.py": "print(1)"}, ["python", "escape.py"])
