#!/usr/bin/env python3
"""ChickenButt — tray-toggleable Ollama chat window for GNOME."""

from __future__ import annotations

import os
import sys

# Allow running from any cwd
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib

from ollama_client import OllamaClient
from release_info import APP_ID, APP_NAME
from tray import TrayIcon
from window import ChatSidebar


class ChickenButtApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window: ChatSidebar | None = None
        self.tray: TrayIcon | None = None
        self.connect("activate", self._on_activate)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self._quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def _on_activate(self, *_args) -> None:
        if self.window is None:
            self.window = ChatSidebar(self, client=OllamaClient())
            self.window.set_close_handler(self._on_window_close)
            # Refresh tray menu enabled state when visibility changes
            self.window.connect("notify::visible", self._on_window_visible)

            # Panel/tray: system chat-bubble symbolic (not the brand chicken —
            # the chick stays on the empty state / app icon / dock).
            tray_icon = self._resolve_tray_chat_icon()

            self.tray = TrayIcon(
                on_show=self._show_window,
                on_hide=self._hide_window,
                on_toggle=self._toggle_window,
                on_quit=self._quit,
                on_clear=self._clear_chat,
                is_visible=self._window_is_visible,
                icon_name=tray_icon,
                # Empty theme path → load from system Adwaita/Yaru icon theme
                icon_theme_path="",
                title=APP_NAME,
            )
            # Window icon: themed name + file fallback for the dock
            self.window.set_icon_name("chickenbutt")
            self._apply_window_icon(self.window)
            ok = self.tray.start()
            if not ok:
                print(
                    "No StatusNotifier host found.\n"
                    "On GNOME, enable App Indicator support for a tray icon.",
                    flush=True,
                )
            else:
                print(
                    "Tray ready.\n"
                    "  Left-click:  Show / Hide / Quit\n"
                    "  Right-click: Show / Hide / Clear / Quit (when host sends ContextMenu)\n"
                    "  Middle-click: toggle window",
                    flush=True,
                )
            self.window.present()
            GLib.idle_add(self._focus_input)
        else:
            self._show_window()

    def _focus_input(self) -> bool:
        if self.window is not None:
            try:
                self.window.input.grab_focus()
            except Exception:  # noqa: BLE001
                pass
        return False

    def _resolve_tray_chat_icon(self) -> str:
        """Pick a chat-bubble style symbolic for the GNOME top-bar indicator."""
        candidates = (
            # Prefer real bubble glyphs when the theme has them (Yaru/Adwaita+)
            "chat-bubbles-empty-symbolic",
            "chat-bubble-text-symbolic",
            "chat-symbolic",
            "chat-message-new-symbolic",  # Adwaita standard
            "internet-chat-symbolic",
            "internet-group-chat",
            "mail-unread-symbolic",
        )
        try:
            from gi.repository import Gdk, Gtk

            display = Gdk.Display.get_default()
            if display is not None:
                theme = Gtk.IconTheme.get_for_display(display)
                for name in candidates:
                    if theme is not None and theme.has_icon(name):
                        return name
        except Exception:  # noqa: BLE001
            pass
        return "chat-message-new-symbolic"

    def _apply_window_icon(self, window) -> None:
        """Ensure dock/task switcher gets the chicken icon, not a generic gear."""
        try:
            from gi.repository import Gdk, Gtk

            display = Gdk.Display.get_default()
            if display is None:
                return
            theme = Gtk.IconTheme.get_for_display(display)
            if theme.has_icon("chickenbutt"):
                window.set_icon_name("chickenbutt")
                return
            # Fallback: load PNG from project tree
            for rel in (
                "icons/hicolor/128x128/apps/chickenbutt.png",
                "icons/chickenbutt-dash-desktop-icon.svg",
                "icons/tray/chickenbutt.png",
            ):
                path = os.path.join(APP_DIR, rel)
                if not os.path.isfile(path):
                    continue
                try:
                    texture = Gdk.Texture.new_from_filename(path)
                    # GTK4 ApplicationWindow: set via default icon list if available
                    if hasattr(window, "set_icon_name"):
                        window.set_icon_name("chickenbutt")
                    # Paint as paintable on the native surface when supported
                    if texture is not None and hasattr(Gtk, "Window"):
                        pass
                except Exception:  # noqa: BLE001
                    continue
                break
        except Exception as exc:  # noqa: BLE001
            print(f"Icon setup: {exc}", flush=True)

    def _window_is_visible(self) -> bool:
        return bool(self.window and self.window.is_visible())

    def _on_window_visible(self, *_args) -> None:
        if self.tray:
            self.tray.notify_visibility_changed()

    def _on_window_close(self) -> bool:
        self._hide_window()
        return True

    def _show_window(self) -> None:
        if self.window is None:
            return
        if self.tray:
            self.tray.prepare_primary_menu()
        self.window.present()
        GLib.idle_add(self._focus_input)

    def _hide_window(self) -> None:
        if self.window is None:
            return
        self.window.set_visible(False)

    def _toggle_window(self) -> None:
        if self.window is None:
            return
        if self.window.is_visible():
            self._hide_window()
        else:
            self._show_window()

    def _clear_chat(self) -> None:
        if self.window is not None:
            self.window.clear_chat()

    def _quit(self) -> None:
        if self.tray:
            self.tray.stop()
        self.quit()


def main() -> int:
    Adw.init()
    # Shown in dock tooltips / about when desktop match works
    GLib.set_application_name(APP_NAME)
    GLib.set_prgname(APP_NAME)
    app = ChickenButtApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
