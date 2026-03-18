from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_dev_local_recreates_infra_after_probe_timeout(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    scripts_dir = project_root / "scripts"
    backend_dir = project_root / "backend"
    frontend_dir = project_root / "frontend"
    venv_bin = project_root / ".venv" / "bin"
    frontend_bin = frontend_dir / "node_modules" / ".bin"
    fake_bin = tmp_path / "fake-bin"
    state_dir = tmp_path / "state"

    scripts_dir.mkdir(parents=True)
    backend_dir.mkdir()
    frontend_bin.mkdir(parents=True)
    venv_bin.mkdir(parents=True)
    fake_bin.mkdir()
    state_dir.mkdir()

    source_script = Path(__file__).resolve().parents[3] / "scripts" / "dev-local.sh"
    target_script = scripts_dir / "dev-local.sh"
    target_script.write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")
    target_script.chmod(target_script.stat().st_mode | stat.S_IXUSR)

    (project_root / ".env").write_text("DB_PASSWORD=test-password\n", encoding="utf-8")
    (state_dir / "probe-count").write_text("0", encoding="utf-8")
    (state_dir / "docker.log").write_text("", encoding="utf-8")

    _write_executable(
        venv_bin / "python",
        f"""#!/usr/bin/env python3
from pathlib import Path
import os
import sys

state_dir = Path({str(state_dir)!r})
probe_file = state_dir / "probe-count"
count = int(probe_file.read_text(encoding="utf-8"))
probe_file.write_text(str(count + 1), encoding="utf-8")
if not (state_dir / "recreated").exists() and count < 60:
    raise SystemExit(1)
raise SystemExit(0)
""",
    )
    _write_executable(venv_bin / "alembic", "#!/bin/sh\nexit 0\n")
    _write_executable(venv_bin / "uvicorn", "#!/bin/sh\nexit 0\n")
    _write_executable(frontend_bin / "next", "#!/bin/sh\nexit 0\n")

    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env python3
from pathlib import Path
import sys

state_dir = Path({str(state_dir)!r})
log_file = state_dir / "docker.log"
argv = sys.argv[1:]
log_file.write_text(log_file.read_text(encoding="utf-8") + " ".join(argv) + "\\n", encoding="utf-8")

if argv == ["compose", "up", "-d", "--force-recreate", "postgres", "redis"]:
    (state_dir / "recreated").write_text("1", encoding="utf-8")

if argv[:3] == ["compose", "logs", "postgres"]:
    print("postgres logs placeholder")
""",
    )
    _write_executable(fake_bin / "npm", "#!/bin/sh\nexit 0\n")
    _write_executable(fake_bin / "sleep", "#!/bin/sh\nexit 0\n")

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(target_script)],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    docker_log = (state_dir / "docker.log").read_text(encoding="utf-8")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "compose up -d postgres redis" in docker_log
    assert "compose up -d --force-recreate postgres redis" in docker_log
