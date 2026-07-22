#!/usr/bin/env python3
"""Install the ChickenButt .desktop entry for the current user.

The tracked <APP_ID>.desktop uses an @REPO_DIR@ placeholder in its Exec=
line instead of a hardcoded path, since that path is machine-specific.
This script fills it in with the actual clone location and installs the
result to ~/.local/share/applications/.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from release_info import APP_ID  # noqa: E402

DESKTOP_FILENAME = f"{APP_ID}.desktop"
SRC = os.path.join(ROOT, DESKTOP_FILENAME)
DEST_DIR = os.path.expanduser("~/.local/share/applications")
DEST = os.path.join(DEST_DIR, DESKTOP_FILENAME)


def main() -> int:
    with open(SRC, encoding="utf-8") as f:
        contents = f.read()

    contents = contents.replace("@REPO_DIR@", ROOT)

    os.makedirs(DEST_DIR, exist_ok=True)
    with open(DEST, "w", encoding="utf-8") as f:
        f.write(contents)

    print(f"Installed {DEST}")
    print("Run scripts/install-icons.py too if you haven't already.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
