from __future__ import annotations

import json
from pathlib import Path

from app.destinations.config import DESTINATION_PRESETS
from app.sinks.rss import DEFAULT_SITE_URL, _resolve_site_url


def test_local_frontend_port_defaults_use_3018() -> None:
    root = Path(__file__).resolve().parents[2]
    package_json = json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))

    assert package_json["scripts"]["dev"] == "next dev --port 3018"
    assert DESTINATION_PRESETS["rss"]["default_config"]["site_url"] == "http://localhost:3018"
    assert DEFAULT_SITE_URL == "http://localhost:3018"
    assert _resolve_site_url(raw=None, feed_url="http://localhost:8000/api/v1/feed.xml") == "http://localhost:3018"

    doctor_script = (root / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    dev_local_script = (root / "scripts" / "dev-local.sh").read_text(encoding="utf-8")

    assert "check_port 3018" in doctor_script
    assert "Starting frontend on :3018" in dev_local_script
