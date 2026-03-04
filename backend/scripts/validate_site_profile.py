"""Validate site profile schema and P0 profile coverage."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "app" / "collectors" / "site_profiles"
PRESETS_PATH = ROOT / "app" / "collectors" / "source_presets.yaml"

sys.path.insert(0, str(ROOT))

from app.collectors.site_profile_loader import validate_site_profile  # noqa: E402


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def validate_profile_file(path: Path) -> tuple[bool, str]:
    try:
        payload = load_yaml(path)
        validate_site_profile(payload)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def expected_p0_profile_keys() -> list[str]:
    presets = load_yaml(PRESETS_PATH)
    keys: list[str] = []
    for source in presets.get("sources", []):
        if not isinstance(source, dict):
            continue
        if source.get("priority") != "p0" or not source.get("enabled"):
            continue
        if source.get("rss_url"):
            continue
        urls = [u for u in (source.get("urls") or []) if isinstance(u, str) and u.strip()]
        if not urls:
            continue
        keys.append(str(source.get("key") or ""))
    return sorted({k for k in keys if k})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=str, help="Single profile path to validate")
    parser.add_argument("--all", action="store_true", help="Validate all profile files")
    parser.add_argument("--check-p0", action="store_true", help="Check P0 expected profiles are present")
    args = parser.parse_args()

    exit_code = 0

    if args.profile:
        path = Path(args.profile)
        ok, message = validate_profile_file(path)
        print(f"[{ 'ok' if ok else 'fail' }] {path}: {message}")
        return 0 if ok else 1

    if args.all:
        for path in sorted(PROFILE_DIR.glob("*.yaml")):
            ok, message = validate_profile_file(path)
            print(f"[{ 'ok' if ok else 'fail' }] {path.name}: {message}")
            if not ok:
                exit_code = 1

    if args.check_p0:
        expected = set(expected_p0_profile_keys())
        actual = {path.stem for path in PROFILE_DIR.glob("*.yaml")}
        missing = sorted(expected - actual)
        if missing:
            print(f"[fail] missing p0 profiles: {', '.join(missing)}")
            exit_code = 1
        else:
            print(f"[ok] p0 profile coverage complete ({len(expected)} profiles)")

    if not (args.profile or args.all or args.check_p0):
        parser.print_help()
        return 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
