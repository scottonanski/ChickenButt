"""WebKitGTK transcript surface for ChickenButt (spike).

Presentation-only page under web/; Python posts JSON events and handles intents.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, GLib, Gtk, WebKit


WEB_DIR = Path(__file__).resolve().parent / "web"


class WebTranscriptView(Gtk.Box):
    """One WebKit view for the whole conversation (owns its own scrolling)."""

    def __init__(self, *, on_intent: Callable[[dict[str, Any]], None] | None = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_intent = on_intent
        self._ready = False
        self._queue: list[dict[str, Any]] = []
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._view = WebKit.WebView()
        self._view.set_hexpand(True)
        self._view.set_vexpand(True)

        settings = self._view.get_settings()
        settings.set_enable_developer_extras(True)
        settings.set_javascript_can_access_clipboard(True)

        ucm = self._view.get_user_content_manager()
        ucm.register_script_message_handler("chickenbutt")
        # WebKit 6: detailed signal name may not appear in list_names; try both.
        try:
            ucm.connect(
                "script-message-received::chickenbutt", self._on_script_message
            )
        except TypeError:
            ucm.connect("script-message-received", self._on_script_message)

        self._view.connect("load-changed", self._on_load_changed)

        index = WEB_DIR / "index.html"
        self._view.load_uri(index.as_uri())

        self.append(self._view)

        # Follow Adwaita color scheme
        try:
            sm = Adw.StyleManager.get_default()
            sm.connect("notify::dark", self._on_theme)
            self._apply_theme(sm.get_dark())
        except Exception:
            pass

    def _on_theme(self, sm: Adw.StyleManager, *_args) -> None:
        self._apply_theme(sm.get_dark())

    def _apply_theme(self, dark: bool) -> None:
        self.post({"type": "theme_changed", "theme": "dark" if dark else "light"})

    def _on_load_changed(self, _view, event) -> None:
        if event == WebKit.LoadEvent.FINISHED:
            self._ready = True
            # flush queued events
            pending, self._queue = self._queue, []
            for ev in pending:
                self._eval_event(ev)
            try:
                sm = Adw.StyleManager.get_default()
                self._apply_theme(sm.get_dark())
            except Exception:
                pass

    def _on_script_message(self, _ucm, message) -> None:
        try:
            value = message
            if hasattr(message, "get_js_value"):
                value = message.get_js_value()
            raw = None
            if hasattr(value, "to_json"):
                try:
                    raw = value.to_json(0)
                except Exception:
                    raw = None
            if raw is None and hasattr(value, "to_string"):
                raw = value.to_string()
            if raw is None:
                raw = str(value)
            if not raw:
                return
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                # postMessage may pass a plain object already as JSON-ish string
                payload = {"type": "unknown", "raw": raw}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {"type": "unknown", "raw": payload}
            if self._on_intent and isinstance(payload, dict):
                GLib.idle_add(self._on_intent, payload)
        except Exception as exc:  # noqa: BLE001
            print(f"transcript intent error: {exc}", flush=True)

    def post(self, event: dict[str, Any]) -> None:
        """Send a structured event to the page (main thread)."""
        if not self._ready:
            self._queue.append(event)
            return
        self._eval_event(event)

    def _eval_event(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        # Safe string for JS single-quoted argument
        js = f"window.chickenbuttApplyJson({json.dumps(payload)});"
        try:
            self._view.evaluate_javascript(js, -1, None, None, None, None, None)
        except TypeError:
            # Older signature variants
            try:
                self._view.evaluate_javascript(js, len(js), None, None, None, None)
            except Exception as exc:  # noqa: BLE001
                print(f"evaluate_javascript failed: {exc}", flush=True)

    def reset(self, messages: list[dict[str, str]] | None = None) -> None:
        payload_messages = []
        if messages:
            for i, m in enumerate(messages):
                payload_messages.append(
                    {
                        "id": m.get("id") or f"hist-{i}",
                        "role": m.get("role", "assistant"),
                        "content": m.get("content", ""),
                    }
                )
        self.post({"type": "conversation_reset", "messages": payload_messages})
