#!/usr/bin/env python3
"""Regression: release_info is the single source of truth for ChickenButt's
public identity, and everything that must agree with it actually does —
the real GApplication's application_id, the tracked desktop entry's
filename and StartupWMClass, and the installer's real output.

Real ChickenButtApp construction and a real subprocess run of the actual
installer script (against a throwaway HOME) — no mocking of the code
under test.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

import release_info  # noqa: E402


class Results:
    def __init__(self) -> None:
        self.ok: list[str] = []
        self.fail: list[str] = []

    def check(self, name: str, cond: bool, detail: str = "") -> None:
        if cond:
            self.ok.append(name)
            print(f"  PASS  {name}" + (f" — {detail}" if detail else ""), flush=True)
        else:
            self.fail.append(name)
            print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""), flush=True)


REVERSE_DNS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(\.[A-Za-z][A-Za-z0-9]*){2,}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def parse_desktop_entry(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        entries[key.strip()] = value.strip()
    return entries


def main() -> int:
    results = Results()

    print("\n[1] release_info is well-formed", flush=True)
    results.check(
        "APP_ID looks like a reverse-DNS identifier",
        bool(REVERSE_DNS_RE.match(release_info.APP_ID)),
        release_info.APP_ID,
    )
    results.check(
        "APP_ID is not the old dev.local placeholder",
        "dev.local" not in release_info.APP_ID.lower(),
        release_info.APP_ID,
    )
    results.check("APP_NAME is 'ChickenButt'", release_info.APP_NAME == "ChickenButt")
    results.check(
        "VERSION is a valid semver-shaped string",
        bool(SEMVER_RE.match(release_info.VERSION)),
        release_info.VERSION,
    )

    print("\n[2] main.py's real GApplication uses release_info.APP_ID", flush=True)
    import main as main_module

    results.check(
        "main.APP_ID is exactly release_info.APP_ID (single source, not a copy)",
        main_module.APP_ID == release_info.APP_ID,
        main_module.APP_ID,
    )
    Adw.init()
    app = main_module.ChickenButtApp()
    results.check(
        "constructed ChickenButtApp's real application_id matches release_info.APP_ID",
        app.get_application_id() == release_info.APP_ID,
        app.get_application_id(),
    )

    print("\n[3] Tracked desktop entry file matches APP_ID", flush=True)
    desktop_filename = f"{release_info.APP_ID}.desktop"
    desktop_path = APP_DIR / desktop_filename
    results.check(
        f"tracked desktop file exists at repo root: {desktop_filename}",
        desktop_path.is_file(),
        str(desktop_path),
    )
    old_stray = APP_DIR / "dev.local.ChickenButt.desktop"
    results.check(
        "old dev.local.ChickenButt.desktop no longer present (renamed, not duplicated)",
        not old_stray.exists(),
        str(old_stray),
    )
    entries = parse_desktop_entry(desktop_path.read_text(encoding="utf-8")) if desktop_path.is_file() else {}
    results.check(
        "desktop entry StartupWMClass matches release_info.APP_ID",
        entries.get("StartupWMClass") == release_info.APP_ID,
        entries.get("StartupWMClass"),
    )
    results.check(
        "desktop entry Name matches release_info.APP_NAME",
        entries.get("Name") == release_info.APP_NAME,
        entries.get("Name"),
    )
    # The desktop entry's Version= key is the Desktop Entry Specification
    # version this file conforms to, NOT ChickenButt's own release version
    # — they are unrelated fields that happen to share a key name. This
    # guards against someone "fixing" it to track release_info.VERSION.
    results.check(
        "desktop entry Version stays the desktop-entry-spec version ('1.0'), "
        "not release_info.VERSION",
        entries.get("Version") == "1.0",
        entries.get("Version"),
    )

    print("\n[4] The real installer script produces a consistent, working install", flush=True)
    with tempfile.TemporaryDirectory(prefix="cb-release-identity-") as tmp_home:
        env = dict(os.environ)
        env["HOME"] = tmp_home
        proc = subprocess.run(
            [sys.executable, str(APP_DIR / "scripts" / "install-desktop-entry.py")],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        results.check("installer script exits 0", proc.returncode == 0, proc.stderr[-500:])
        installed_path = Path(tmp_home) / ".local" / "share" / "applications" / desktop_filename
        results.check(
            "installer wrote the desktop file under the APP_ID-derived filename",
            installed_path.is_file(),
            str(installed_path),
        )
        installed_entries = (
            parse_desktop_entry(installed_path.read_text(encoding="utf-8"))
            if installed_path.is_file()
            else {}
        )
        results.check(
            "installed entry's StartupWMClass matches release_info.APP_ID",
            installed_entries.get("StartupWMClass") == release_info.APP_ID,
            installed_entries.get("StartupWMClass"),
        )
        results.check(
            "installer resolved @REPO_DIR@ to the real repo path",
            installed_entries.get("Exec") == f"{APP_DIR}/run.sh",
            installed_entries.get("Exec"),
        )

    print("\n=== Summary ===", flush=True)
    print(f"Passed: {len(results.ok)}  Failed: {len(results.fail)}", flush=True)
    for f in results.fail:
        print(f"  - {f}", flush=True)
    return 1 if results.fail else 0


if __name__ == "__main__":
    try:
        code = main()
        os._exit(code)
    except Exception:
        import traceback

        traceback.print_exc()
        os._exit(2)
