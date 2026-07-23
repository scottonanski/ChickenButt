#!/usr/bin/env python3
"""Regenerate ChickenButt's tracked private icon assets (FreeDesktop hicolor
layout) from their SVG sources. Source-asset generator only — it writes
exclusively into the tracked project tree (icons/hicolor/, icons/tray/) and
never touches the user's home directory or system icon caches. Commit the
regenerated files like any other source change.

The public, installed application icon is a separate concern: Meson installs
icons/chickenbutt-dash-desktop-icon.svg directly under
share/icons/hicolor/scalable/apps/<APP_ID>.svg at `meson install` time (see
meson.build) and runs gtk-update-icon-cache there when available — this
script has nothing to do with that path.

Sources (in icons/):
  chickenbutt-dash-desktop-icon.svg  → app grid / window icon (full color)
  chickenbutt-light-icon.svg         → tray on dark panels (white chick)
  chickenbutt-dark-icon.svg          → tray on light panels (black chick)

Regenerates (in icons/, tracked in git):
  icons/hicolor/...          (private project-tree mirror; see main.py's
                               APP_DIR-relative fallback icon paths)
  icons/tray/...             (StatusNotifier IconThemePath)
"""

from __future__ import annotations

import os
import shutil
import sys

import gi

gi.require_version("Rsvg", "2.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Rsvg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "icons")
APP_SVG = os.path.join(ICONS, "chickenbutt-dash-desktop-icon.svg")
TRAY_LIGHT = os.path.join(ICONS, "chickenbutt-light-icon.svg")
TRAY_DARK = os.path.join(ICONS, "chickenbutt-dark-icon.svg")
HICOLOR = os.path.join(ICONS, "hicolor")
TRAY_DIR = os.path.join(ICONS, "tray")
SIZES = [16, 22, 24, 32, 48, 64, 128, 256]


def render_svg(svg_path: str, size: int, out_png: str) -> None:
    """Rasterize SVG at an exact pixel size (not natural 16px then upscale)."""
    if not os.path.isfile(svg_path):
        raise FileNotFoundError(svg_path)
    # Prefer size-aware load so vectors stay sharp on 22–128px tray/dock sizes.
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file_at_size(svg_path, size, size)
    except Exception:
        pb = None
    if pb is None:
        handle = Rsvg.Handle.new_from_file(svg_path)
        pb = handle.get_pixbuf()
        if pb is None:
            raise RuntimeError(f"Could not render {svg_path}")
        if pb.get_width() != size or pb.get_height() != size:
            pb = pb.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
    elif pb.get_width() != size or pb.get_height() != size:
        pb = pb.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    pb.savev(out_png, "png", [], [])
    print(f"  {out_png} ({size}x{size})")


def main() -> int:
    for p in (APP_SVG, TRAY_LIGHT, TRAY_DARK):
        if not os.path.isfile(p):
            print(f"Missing source icon: {p}", file=sys.stderr)
            return 1

    print("App icon (dash / window)…")
    scalable = os.path.join(HICOLOR, "scalable", "apps", "chickenbutt.svg")
    os.makedirs(os.path.dirname(scalable), exist_ok=True)
    shutil.copy2(APP_SVG, scalable)

    for size in SIZES:
        rel = f"{size}x{size}/apps/chickenbutt.png"
        render_svg(APP_SVG, size, os.path.join(HICOLOR, rel))

    print("Tray icons…")
    os.makedirs(TRAY_DIR, exist_ok=True)
    # Flat IconThemePath only resolves name.png / name.svg — use large PNGs so
    # the panel can downscale a full glyph (small 16x16 SVGs look like dots).
    # Default tray: light glyph (reads well on dark GNOME top bar)
    for size, name in (
        (64, "chickenbutt.png"),
        (128, "chickenbutt@2.png"),
        (64, "chickenbutt-light.png"),
        (128, "chickenbutt-light@2.png"),
        (64, "chickenbutt-dark.png"),
        (128, "chickenbutt-dark@2.png"),
        (64, "chickenbutt-symbolic.png"),
    ):
        src = TRAY_DARK if "dark" in name else TRAY_LIGHT
        render_svg(src, size, os.path.join(TRAY_DIR, name))
    # Keep SVG copies for hosts that prefer vectors, but PNGs are primary.
    shutil.copy2(TRAY_LIGHT, os.path.join(TRAY_DIR, "chickenbutt.svg"))
    shutil.copy2(TRAY_LIGHT, os.path.join(TRAY_DIR, "chickenbutt-light.svg"))
    shutil.copy2(TRAY_DARK, os.path.join(TRAY_DIR, "chickenbutt-dark.svg"))

    # Ensure index.theme exists for local tree
    index = os.path.join(HICOLOR, "index.theme")
    if not os.path.isfile(index):
        print("  (no index.theme - optional for project tree)")

    print("Done. Regenerated tracked assets under icons/hicolor/ and icons/tray/.")
    print("Commit the changes like any other source update.")
    print("The public installed icon comes from meson install, not this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
