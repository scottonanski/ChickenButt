"""ChickenButt chat window (GTK4 + libadwaita) — messaging-style UI."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from conversation_store import ConversationStore
from message_widgets import MessageBody, ensure_md_css
from ollama_client import OllamaClient, OllamaError
from ollama_health import (
    HealthKind,
    HealthState,
    checking_state,
    classify_error,
    probe_ollama,
)


DEFAULT_WIDTH = 780
DEFAULT_HEIGHT = 720
SIDEBAR_WIDTH = 220
# Model DropDown closed-pill width (and list popup). ~2x the old content-hug size.
MODEL_DROPDOWN_WIDTH = 320

# Composer: visible height vs content length are independent.
# Grow 1→N lines, then scroll inside; paste may be huge without eating the window.
COMPOSER_MIN_LINES = 1
COMPOSER_MAX_LINES = 8
COMPOSER_COMPACT_MAX_LINES = 6
# Window height at/below this uses the compact line cap (small displays / short windows).
COMPOSER_COMPACT_WINDOW_HEIGHT = 560
# Hard technical safety cap (not a product "short prompt" limit).
COMPOSER_CHAR_LIMIT = 64_000
# Show a character counter once the draft is this fraction of the hard cap.
# (Later: also surface near selected model context capacity.)
COMPOSER_COUNTER_SHOW_RATIO = 0.85

# Prefer last successfully loaded model on next launch
_SETTINGS_DIR = Path(GLib.get_user_config_dir()) / "chickenbutt"
_SETTINGS_PATH = _SETTINGS_DIR / "settings.json"


def _read_settings() -> dict:
    try:
        if _SETTINGS_PATH.is_file():
            data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {}


def _write_settings(data: dict) -> None:
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        _SETTINGS_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"settings save failed: {exc}", flush=True)


def _load_last_model() -> str | None:
    name = _read_settings().get("last_model")
    return name if isinstance(name, str) and name.strip() else None


def _save_last_model(model: str) -> None:
    if not model or not model.strip():
        return
    data = _read_settings()
    if data.get("last_model") == model:
        return
    data["last_model"] = model
    _write_settings(data)


def _load_sidebar_open() -> bool:
    """Default open — chat history is primary navigation."""
    val = _read_settings().get("sidebar_open")
    if val is None:
        return True
    return bool(val)


def _save_sidebar_open(open_: bool) -> None:
    data = _read_settings()
    if data.get("sidebar_open") is open_:
        return
    data["sidebar_open"] = bool(open_)
    _write_settings(data)


def _pick_startup_model(models: list[str], preferred: str | None) -> int:
    """Index of last-loaded model if still installed; else 0."""
    if not models:
        return 0
    if preferred and preferred in models:
        return models.index(preferred)
    # Soft match: same base name (e.g. tag drift :latest vs :8b)
    if preferred:
        base = preferred.split(":")[0]
        for i, name in enumerate(models):
            if name == preferred or name.split(":")[0] == base:
                return i
    return 0


def _transcript_mode() -> str:
    """webkit (default) | native — from CHICKENBUTT_TRANSCRIPT env."""
    raw = (os.environ.get("CHICKENBUTT_TRANSCRIPT") or "webkit").strip().lower()
    if raw in ("native", "gtk"):
        return "native"
    return "webkit"

APP_CSS = b"""
/* ---- chat surface (solid, matches WebKit --bg) ---- */
.chat-surface {
    background-color: #121216;
}
.chat-list {
    background: transparent;
}

/* ---- empty state ---- */
.empty-state {
    opacity: 0.95;
}
.empty-title {
    font-size: 1.15em;
    font-weight: 700;
    margin-top: 10px;
    color: alpha(white, 0.88);
}
.empty-sub {
    opacity: 0.55;
    margin-top: 18px; /* space under greeting title */
    color: alpha(white, 0.7);
}
.empty-icon {
    opacity: 0.92;
    margin-bottom: 6px;
    min-width: 64px;
    min-height: 64px;
}

/* ---- message row ---- */
.msg-row {
    margin-top: 2px;
    margin-bottom: 2px;
}
.msg-row-user {
    margin-left: 24px;
}
.msg-row-assistant {
    /* full-width assistant bubbles */
    margin-right: 0;
}

/* ---- bubbles ---- */
.chat-bubble {
    border-radius: 16px;
    padding: 10px 14px;
    min-width: 40px;
    font-size: 15px;
}
.chat-user {
    background-color: @accent_bg_color;
    color: @accent_fg_color;
    /* Speech-tail: sharp lower-right corner */
    border-bottom-right-radius: 0;
    box-shadow: 0 1px 3px alpha(black, 0.3);
}
.chat-assistant {
    /* No fill - assistant text sits on the chat surface */
    background-color: transparent;
    color: alpha(white, 0.92);
    border-radius: 0;
    box-shadow: none;
    padding-left: 0;
    padding-right: 0;
}
.chat-error {
    background-color: alpha(@error_color, 0.18);
    border: 1px solid alpha(@error_color, 0.35);
}

.chat-body {
    font-size: 15px;
    line-height: 1.5;
}
.chat-user .chat-body {
    color: @accent_fg_color;
}
.chat-meta {
    font-size: 0.7em;
    opacity: 0.45;
    margin-top: 3px;
    margin-left: 4px;
    margin-right: 4px;
    color: alpha(white, 0.7);
}
.chat-user-meta {
    opacity: 0.55;
    color: alpha(white, 0.75);
}

/* typing indicator */
.typing-dots {
    font-weight: 700;
    letter-spacing: 0.12em;
    opacity: 0.55;
}

/* ---- model toolbar (dropdown only; refresh is in the header) ---- */
.model-toolbar {
    background: transparent;
    padding: 0;
    border: none;
}
/* Closed pill + open list share this width (~2x the old content-sized pill). */
.model-toolbar dropdown {
    min-height: 38px;
    min-width: 320px;
    border-radius: 10px;
}

/* ---- composer (floats on chat surface) ---- */
.composer-bar {
    /* No separate chrome - shares chat-surface so the pill floats */
    background-color: transparent;
    background-image: none;
    padding: 6px 12px 16px 12px;
    border-top: none;
}
.composer-shell {
    background-color: alpha(white, 0.10);
    border-radius: 22px;
    border: 1px solid alpha(white, 0.10);
    padding: 4px 4px 4px 12px;
    box-shadow: 0 4px 18px alpha(black, 0.35), 0 1px 3px alpha(black, 0.25);
}
.composer-shell:focus-within {
    border-color: alpha(@accent_bg_color, 0.55);
    background-color: alpha(white, 0.12);
    box-shadow: 0 6px 22px alpha(black, 0.4), 0 0 0 1px alpha(@accent_bg_color, 0.15);
}
.composer-input {
    background: transparent;
    border: none;
    box-shadow: none;
    font-size: 0.95em;
}
.composer-input textview,
.composer-input text {
    background: transparent;
    color: alpha(white, 0.92);
}
.composer-scroll {
    background: transparent;
    border: none;
    box-shadow: none;
    min-width: 0;
}
.composer-scroll > scrollbar {
    margin: 0;
}
.composer-hint {
    font-size: 0.72em;
    opacity: 0.42;
    color: alpha(white, 0.7);
    margin-bottom: 8px;
    transition: opacity 280ms ease;
}
.composer-hint.faded {
    opacity: 0;
}
.composer-meta-row {
    margin-top: 4px;
    margin-left: 6px;
    margin-right: 6px;
    min-height: 0;
}
.composer-char-count {
    font-size: 0.72em;
    opacity: 0.55;
    color: alpha(white, 0.7);
}
.composer-char-count.warning {
    opacity: 0.9;
    color: @warning_color;
}
.send-btn {
    min-width: 36px;
    min-height: 36px;
    padding: 0;
    border-radius: 999px;
}
.send-btn.suggested-action {
    background-color: @accent_bg_color;
    color: @accent_fg_color;
}
.stop-btn {
    min-width: 36px;
    min-height: 36px;
    padding: 0;
    border-radius: 999px;
}

/* header subtitle look */
.header-title {
    font-weight: 700;
}
.header-sub {
    font-size: 0.78em;
    opacity: 0.6;
}

/* ---- model load overlay ---- */
.load-overlay {
    background-color: alpha(black, 0.62);
}
.load-card {
    background-color: alpha(@window_bg_color, 0.97);
    border-radius: 18px;
    padding: 28px 32px;
    min-width: 280px;
    border: 1px solid alpha(@window_fg_color, 0.10);
    box-shadow: 0 12px 40px alpha(black, 0.45);
}
.load-title {
    font-size: 1.05em;
    font-weight: 700;
}
.load-model {
    font-size: 0.95em;
    opacity: 0.9;
    margin-top: 4px;
}
.load-status {
    font-size: 0.82em;
    opacity: 0.55;
    margin-top: 10px;
}
.load-progress {
    margin-top: 14px;
    min-width: 220px;
}

/* ---- docked chat history rail (GNOME-style, no modal overlay) ---- */
.chat-sidebar {
    background-color: alpha(@window_fg_color, 0.03);
    border-right: 1px solid alpha(@window_fg_color, 0.10);
}
.chat-sidebar-header {
    padding: 6px 8px 6px 12px;
    min-height: 40px;
    border-bottom: 1px solid alpha(@window_fg_color, 0.08);
}
.chat-sidebar-title {
    font-weight: 700;
    font-size: 0.95em;
}
.chat-sidebar-section {
    font-size: 0.72em;
    font-weight: 600;
    opacity: 0.55;
    margin: 8px 14px 4px 14px;
    letter-spacing: 0.02em;
}
.chat-sidebar-footer {
    padding: 6px 8px;
    border-top: 1px solid alpha(@window_fg_color, 0.08);
    min-height: 40px;
}
.chat-sidebar list {
    background: transparent;
}
.chat-sidebar row {
    border-radius: 10px;
    margin: 1px 8px;
    padding: 0;
    min-height: 0;
}
.chat-sidebar row:hover {
    background-color: alpha(@window_fg_color, 0.06);
}
.chat-sidebar row:selected {
    background-color: alpha(@accent_bg_color, 0.20);
}
.chat-sidebar-row-title {
    font-weight: 500;
    font-size: 0.92em;
}
.chat-sidebar-row-active {
    font-weight: 700;
}
.chat-sidebar-row-meta {
    font-size: 0.75em;
    opacity: 0.5;
}
/* Overflow actions: calm until hover/selection */
.chat-sidebar-row-actions {
    opacity: 0;
    transition: opacity 0.12s ease;
}
.chat-sidebar row:hover .chat-sidebar-row-actions,
.chat-sidebar row:selected .chat-sidebar-row-actions,
.chat-sidebar-row-actions:focus-within {
    opacity: 1;
}
.chat-sidebar-row-actions button {
    min-width: 28px;
    min-height: 28px;
    padding: 0;
}

/* ---- Ollama health / onboarding banner ---- */
.health-banner {
    background-color: alpha(@accent_bg_color, 0.12);
    border: 1px solid alpha(@accent_bg_color, 0.28);
    border-radius: 12px;
    padding: 10px 12px;
    margin-top: 4px;
    margin-bottom: 4px;
}
.health-banner.error {
    background-color: alpha(@error_color, 0.12);
    border-color: alpha(@error_color, 0.35);
}
.health-banner.warn {
    background-color: alpha(@warning_color, 0.14);
    border-color: alpha(@warning_color, 0.35);
}
.health-banner-title {
    font-weight: 700;
    font-size: 0.95em;
}
.health-banner-detail {
    font-size: 0.85em;
    opacity: 0.85;
    margin-top: 2px;
}

"""

GREETING_TEXT = "What's up, ChickenButt?"
GREETING_SUB = (
    "Need a model?\n"
    "Type in the box: ollama pull <model-name>"
)

# Composer slash-style commands (run locally; never sent to the LLM).
_RE_OLLAMA_PULL = re.compile(
    r"^ollama\s+pull\s+([A-Za-z0-9][A-Za-z0-9._:/-]*)\s*$",
    re.IGNORECASE,
)
_RE_OLLAMA_LIST = re.compile(r"^ollama\s+list\s*$", re.IGNORECASE)
_RE_OLLAMA_PS = re.compile(r"^ollama\s+ps\s*$", re.IGNORECASE)


def _is_ephemeral_greeting(role: str, content: str) -> bool:
    """Legacy rows may have stored the opener; never treat it as chat context."""
    return role == "assistant" and (content or "").strip() == GREETING_TEXT


def join_continue(seed: str, piece: str) -> str:
    """Append continuation with a single blank-line Markdown boundary.

    Avoids fused text like ``🌐Here's`` and does not stack extra blank lines
    when the seed already ends with newlines.
    """
    seed = (seed or "").rstrip("\r\n")
    piece = (piece or "").lstrip("\r\n")
    if not seed:
        return piece
    if not piece:
        return seed
    return seed + "\n\n" + piece


def continue_seed_for_stream(seed: str) -> str:
    """Seed text for the transcript when starting a continue stream."""
    seed = (seed or "").rstrip("\r\n")
    if not seed:
        return ""
    return seed + "\n\n"


class ChatSidebar(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, client: OllamaClient | None = None):
        super().__init__(application=app, title="ChickenButt")
        self.client = client or OllamaClient()
        self._store = ConversationStore()
        self._conversation_id: str | None = None
        self._messages: list[dict[str, str]] = []
        self._streaming = False
        self._stream_generation = 0
        self._active_stream_cancel: threading.Event | None = None
        self._model: str | None = None
        self._on_close_request: Callable[[], bool] | None = None
        self._empty_box: Gtk.Widget | None = None
        self._status_label: Gtk.Label | None = None
        self._transcript_mode = _transcript_mode()
        self._web: object | None = None  # WebTranscriptView when mode=webkit
        self._msg_counter = 0
        self._loading_model = False
        self._stop_load = False
        self._load_pulse_id: int = 0
        self._load_indeterminate = True
        self._greeted_models: set[str] = set()
        self._suppress_model_select = False
        self._history_restored = False
        self._load_overlay: Gtk.Widget | None = None
        self._load_title: Gtk.Label | None = None
        self._load_model_label: Gtk.Label | None = None
        self._load_status: Gtk.Label | None = None
        self._load_progress: Gtk.ProgressBar | None = None
        self._load_spinner: Gtk.Spinner | None = None
        self._root_overlay: Gtk.Overlay | None = None
        self.model_combo: Gtk.DropDown | None = None
        self.send_btn: Gtk.Button | None = None
        self.stop_btn: Gtk.Button | None = None
        self.input: Gtk.TextView | None = None
        self._input_scroll: Gtk.ScrolledWindow | None = None
        self._composer_char_label: Gtk.Label | None = None
        self._composer_hint: Gtk.Label | None = None
        self._composer_hint_fade_id: int = 0
        self._composer_truncating = False
        self._empty_icon: Gtk.Widget | None = None
        self._refresh_btn: Gtk.Button | None = None
        self._clear_btn: Gtk.Button | None = None
        self._new_chat_btn: Gtk.Button | None = None
        self._sidebar_new_btn: Gtk.Button | None = None
        self._settings_btn: Gtk.Button | None = None
        self._sidebar_btn: Gtk.ToggleButton | None = None
        self._sidebar: Gtk.Widget | None = None
        self._history_list: Gtk.ListBox | None = None
        self._sidebar_syncing = False
        self._history_dirty = True  # rebuild list only when data changes
        self._chat_title_label: Gtk.Label | None = None
        self._load_failed = False
        self._load_generation = 0
        self._health: HealthState = checking_state()
        self._health_banner: Gtk.Widget | None = None
        self._health_title: Gtk.Label | None = None
        self._health_detail: Gtk.Label | None = None
        self._health_action_btn: Gtk.Button | None = None
        self._health_action_id: str | None = None
        self._health_action_model: str | None = None
        # native: message_id -> row widget (for delete / regenerate)
        self._native_rows: dict[str, Gtk.Widget] = {}

        # Normal floating window (wide enough for docked history rail)
        self.set_default_size(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.set_resizable(True)
        self.set_decorated(True)
        self.set_hide_on_close(True)  # close → tray; Quit from menu
        self.set_size_request(360, 420)

        self._install_css()
        if self._transcript_mode == "native":
            ensure_md_css()
        self._build_ui()
        self.connect("close-request", self._handle_close_request)
        try:
            Adw.StyleManager.get_default().connect(
                "notify::dark", self._sync_empty_brand_icon
            )
        except Exception:  # noqa: BLE001
            pass

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

        # Restore last conversation before model warm-up (so greet skips if history)
        self._restore_history()
        GLib.idle_add(self._refresh_models)

    def set_close_handler(self, handler: Callable[[], bool]) -> None:
        self._on_close_request = handler

    def _handle_close_request(self, *_args) -> bool:
        if self._on_close_request:
            return self._on_close_request()
        self.set_visible(False)
        return True

    def _on_key(self, _controller, keyval, _keycode, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.set_visible(False)
            return True
        return False

    def _install_css(self) -> None:
        css = Gtk.CssProvider()
        css.load_from_data(APP_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(self) -> None:
        # Docked history rail | main chat (push layout — no modal overlay)
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        root.set_hexpand(True)
        root.set_vexpand(True)
        self.set_content(root)

        sidebar = self._build_history_sidebar()
        root.append(sidebar)
        self._sidebar = sidebar

        toolbar_view = Adw.ToolbarView()
        toolbar_view.set_hexpand(True)
        toolbar_view.set_vexpand(True)
        root.append(toolbar_view)

        # ---- standard window header ----
        # No CSD minimize/maximize/close — those live in the app menu
        # (avoids duplicate WM controls depending on desktop setup).
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_box.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label="ChickenButt")
        title.add_css_class("header-title")
        title.set_halign(Gtk.Align.CENTER)
        # Subtitle: conversation title when idle; status while loading/streaming
        self._chat_title_label = Gtk.Label(label="New conversation")
        self._chat_title_label.add_css_class("header-sub")
        self._chat_title_label.set_halign(Gtk.Align.CENTER)
        self._chat_title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._chat_title_label.set_max_width_chars(36)
        self._status_label = self._chat_title_label  # reuse one subtitle line
        title_box.append(title)
        title_box.append(self._chat_title_label)
        header.set_title_widget(title_box)
        toolbar_view.add_top_bar(header)

        # Toggle docked history rail
        sidebar_btn = Gtk.ToggleButton()
        sidebar_btn.set_icon_name("sidebar-show-symbolic")
        sidebar_btn.set_tooltip_text("Show or hide chat list")
        sidebar_btn.set_valign(Gtk.Align.CENTER)
        sidebar_open = _load_sidebar_open()
        sidebar_btn.set_active(sidebar_open)
        sidebar_btn.connect("toggled", self._on_sidebar_toggled)
        header.pack_start(sidebar_btn)
        self._sidebar_btn = sidebar_btn
        sidebar.set_visible(sidebar_open)

        # Clear current conversation (new conversation lives in the sidebar)
        clear_btn = Gtk.Button.new_from_icon_name("edit-clear-all-symbolic")
        clear_btn.set_tooltip_text("Clear conversation")
        clear_btn.set_valign(Gtk.Align.CENTER)
        clear_btn.connect("clicked", lambda *_: self.clear_chat())
        header.pack_start(clear_btn)
        self._clear_btn = clear_btn
        # Header no longer has a New conversation icon (sidebar header only)
        self._new_chat_btn = None

        menu = Gio.Menu()
        menu.append("New Conversation", "win.new-chat")
        menu.append("Show Chat List", "win.toggle-sidebar")
        menu.append("Settings", "win.settings")
        menu.append("Export Chat Markdown…", "win.export-current-md")
        menu.append("Export Chat JSON…", "win.export-current-json")
        # Window controls (replaces header title buttons)
        win_section = Gio.Menu()
        win_section.append("Hide", "win.hide")
        win_section.append("Maximize", "win.maximize")
        win_section.append("Close", "win.close")
        menu.append_section(None, win_section)
        menu.append("Quit", "app.quit")
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_menu_model(menu)
        menu_btn.set_valign(Gtk.Align.CENTER)
        menu_btn.set_tooltip_text("Menu")
        # pack_end: first widget sits at the far right edge
        header.pack_end(menu_btn)

        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh models (Ctrl+R)")
        refresh_btn.add_css_class("flat")
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.set_action_name("win.refresh-models")
        # Immediately left of the burger menu (pack_end: menu first = rightmost)
        header.pack_end(refresh_btn)
        self._refresh_btn = refresh_btn

        # Window actions
        new_action = Gio.SimpleAction.new("new-chat", None)
        new_action.connect("activate", lambda *_: self.new_chat())
        self.add_action(new_action)
        side_action = Gio.SimpleAction.new("toggle-sidebar", None)
        side_action.connect("activate", lambda *_: self.toggle_sidebar())
        self.add_action(side_action)
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", lambda *_: self.open_settings())
        self.add_action(settings_action)
        exp_md = Gio.SimpleAction.new("export-current-md", None)
        exp_md.connect(
            "activate",
            lambda *_: self.export_conversation(self._conversation_id or "", "md"),
        )
        self.add_action(exp_md)
        exp_json = Gio.SimpleAction.new("export-current-json", None)
        exp_json.connect(
            "activate",
            lambda *_: self.export_conversation(self._conversation_id or "", "json"),
        )
        self.add_action(exp_json)

        hide_action = Gio.SimpleAction.new("hide", None)
        hide_action.connect("activate", lambda *_: self.hide_to_tray())
        self.add_action(hide_action)
        max_action = Gio.SimpleAction.new("maximize", None)
        max_action.connect("activate", lambda *_: self.toggle_maximize())
        self.add_action(max_action)
        close_action = Gio.SimpleAction.new("close", None)
        close_action.connect("activate", lambda *_: self.hide_to_tray())
        self.add_action(close_action)
        refresh_action = Gio.SimpleAction.new("refresh-models", None)
        refresh_action.connect("activate", lambda *_: self._refresh_models())
        self.add_action(refresh_action)
        self._refresh_action = refresh_action

        # Accels show as shortcut text on the right of menu rows (GNOME menu model).
        app = self.get_application()
        if app is not None:
            app.set_accels_for_action("win.hide", ["Escape"])
            app.set_accels_for_action("win.maximize", ["F11"])
            app.set_accels_for_action("win.close", ["<Primary>w"])
            app.set_accels_for_action("win.refresh-models", ["<Primary>r"])
            # app.quit already has <Control>q from main.py

        # Model selector: fixed pill width (list popup matches the button).
        model_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        model_row.add_css_class("model-toolbar")
        model_row.set_halign(Gtk.Align.CENTER)
        model_row.set_hexpand(True)
        model_row.set_valign(Gtk.Align.CENTER)

        self.model_combo = Gtk.DropDown.new_from_strings(["Loading models…"])
        self.model_combo.set_hexpand(False)
        self.model_combo.set_halign(Gtk.Align.CENTER)
        self.model_combo.set_valign(Gtk.Align.CENTER)
        # Force closed-pill width; Gtk.DropDown sizes to content otherwise.
        self.model_combo.set_size_request(MODEL_DROPDOWN_WIDTH, 38)
        self.model_combo.connect("notify::selected", self._on_model_selected)
        model_row.append(self.model_combo)

        model_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        model_bar.set_hexpand(True)
        model_bar.set_margin_top(10)
        model_bar.set_margin_bottom(6)
        model_bar.set_margin_start(24)
        model_bar.set_margin_end(24)
        model_bar.append(model_row)

        # Ollama health / onboarding banner (below model row, above transcript)
        health_clamp = Adw.Clamp()
        health_clamp.set_maximum_size(768)
        health_clamp.set_tightening_threshold(400)
        health_clamp.set_hexpand(True)
        health_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        health_inner.add_css_class("health-banner")
        health_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        health_text.set_hexpand(True)
        self._health_title = Gtk.Label(label="")
        self._health_title.add_css_class("health-banner-title")
        self._health_title.set_halign(Gtk.Align.START)
        self._health_title.set_wrap(True)
        self._health_title.set_xalign(0)
        self._health_detail = Gtk.Label(label="")
        self._health_detail.add_css_class("health-banner-detail")
        self._health_detail.set_halign(Gtk.Align.START)
        self._health_detail.set_wrap(True)
        self._health_detail.set_xalign(0)
        health_text.append(self._health_title)
        health_text.append(self._health_detail)
        health_inner.append(health_text)
        self._health_action_btn = Gtk.Button(label="Retry")
        self._health_action_btn.add_css_class("suggested-action")
        self._health_action_btn.set_valign(Gtk.Align.CENTER)
        self._health_action_btn.connect("clicked", self._on_health_action)
        health_inner.append(self._health_action_btn)
        health_clamp.set_child(health_inner)
        self._health_banner = health_clamp
        self._health_banner.set_visible(False)
        model_bar.append(self._health_banner)

        # ---- message list: native GTK blocks OR WebKit transcript ----
        self.scroller: Gtk.ScrolledWindow | None = None
        self.chat_box: Gtk.Box | None = None
        self._transcript_widget: Gtk.Widget

        if self._transcript_mode == "webkit":
            try:
                from transcript_view import WebTranscriptView

                self._web = WebTranscriptView(on_intent=self._on_web_intent)
                self._transcript_widget = self._web  # type: ignore[assignment]
                print("Transcript: WebKit (default)", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"WebKit transcript unavailable ({exc}); using native.", flush=True)
                self._transcript_mode = "native"
                self._web = None

        if self._transcript_mode == "native":
            self.scroller = Gtk.ScrolledWindow()
            self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            self.scroller.set_vexpand(True)
            self.scroller.set_hexpand(True)
            self.scroller.set_propagate_natural_height(False)
            self.scroller.set_propagate_natural_width(False)
            self.scroller.set_min_content_height(80)
            self.scroller.add_css_class("chat-surface")

            self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.chat_box.add_css_class("chat-list")
            self.chat_box.set_margin_start(12)
            self.chat_box.set_margin_end(12)
            self.chat_box.set_margin_top(8)
            self.chat_box.set_margin_bottom(16)
            self.chat_box.set_valign(Gtk.Align.START)
            self.chat_box.set_vexpand(False)
            self.chat_box.set_hexpand(True)
            self.scroller.set_child(self.chat_box)
            self._transcript_widget = self.scroller
            self._show_empty_state()
            print("Transcript: native GTK (CHICKENBUTT_TRANSCRIPT=native)", flush=True)

        # ---- composer (messaging style), same center column width ----
        composer_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        composer_inner.set_hexpand(True)

        shell = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        shell.add_css_class("composer-shell")
        shell.set_hexpand(True)

        self.input = Gtk.TextView()
        self.input.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.input.set_accepts_tab(False)
        self.input.set_top_margin(8)
        self.input.set_bottom_margin(8)
        self.input.set_left_margin(2)
        self.input.set_right_margin(4)
        self.input.set_pixels_above_lines(1)
        self.input.set_pixels_below_lines(1)
        self.input.set_hexpand(True)
        self.input.set_vexpand(False)
        self.input.add_css_class("composer-input")

        # Visible height capped independently of paste length; overflow scrolls inside.
        # Policy starts NEVER/NEVER: AUTOMATIC vertical reserves ~scrollbar width/height
        # and makes a one-line shell taller than the send button (misaligned).
        self._input_scroll = Gtk.ScrolledWindow()
        self._input_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        self._input_scroll.set_propagate_natural_height(True)
        self._input_scroll.set_propagate_natural_width(True)
        self._input_scroll.set_hexpand(True)
        self._input_scroll.set_vexpand(False)
        self._input_scroll.set_valign(Gtk.Align.CENTER)
        self._input_scroll.add_css_class("composer-scroll")
        self._input_scroll.set_child(self.input)
        self._apply_composer_height()

        # Placeholder via overlay-ish label is hard; set buffer notify for empty look
        self._placeholder = Gtk.Label(label="Message…")
        self._placeholder.add_css_class("dim-label")
        self._placeholder.set_halign(Gtk.Align.START)
        self._placeholder.set_valign(Gtk.Align.CENTER)
        self._placeholder.set_margin_start(4)
        self._placeholder.set_can_target(False)

        input_overlay = Gtk.Overlay()
        input_overlay.set_child(self._input_scroll)
        input_overlay.add_overlay(self._placeholder)
        input_overlay.set_hexpand(True)
        input_overlay.set_vexpand(False)
        input_overlay.set_valign(Gtk.Align.CENTER)

        buf = self.input.get_buffer()
        buf.connect("changed", self._on_buffer_changed)
        buf.connect("insert-text", self._on_composer_insert_text)

        input_key = Gtk.EventControllerKey()
        input_key.connect("key-pressed", self._on_input_key)
        self.input.add_controller(input_key)

        self.stop_btn = Gtk.Button.new_from_icon_name("media-playback-stop-symbolic")
        self.stop_btn.add_css_class("circular")
        self.stop_btn.add_css_class("stop-btn")
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.set_tooltip_text("Stop generating")
        # Center for one-line shell; pin to bottom once the field grows (see _sync_composer_action_valign).
        self.stop_btn.set_valign(Gtk.Align.CENTER)
        self.stop_btn.set_visible(False)
        self.stop_btn.connect("clicked", lambda *_: self._request_stop())

        # Paper-plane send metaphor (Adwaita: mail-send-symbolic; no paper-plane name)
        send_icon = "mail-send-symbolic"
        try:
            display = Gdk.Display.get_default()
            theme = Gtk.IconTheme.get_for_display(display) if display else None
            if theme is not None:
                for candidate in (
                    "paper-plane-symbolic",
                    "mail-send-symbolic",
                    "document-send-symbolic",
                    "go-up-symbolic",
                ):
                    if theme.has_icon(candidate):
                        send_icon = candidate
                        break
        except Exception:  # noqa: BLE001
            pass
        self.send_btn = Gtk.Button.new_from_icon_name(send_icon)
        self.send_btn.add_css_class("circular")
        self.send_btn.add_css_class("send-btn")
        self.send_btn.add_css_class("suggested-action")
        self.send_btn.set_tooltip_text("Send message (Enter)")
        self.send_btn.set_valign(Gtk.Align.CENTER)
        self.send_btn.connect("clicked", lambda *_: self._send())

        shell.append(input_overlay)
        shell.append(self.stop_btn)
        shell.append(self.send_btn)

        # Keyboard hint sits above the floating pill; fades once a chat has messages.
        self._composer_hint = Gtk.Label(
            label="Enter to send · Shift+Enter for newline · Esc to minimize to tray"
        )
        self._composer_hint.add_css_class("composer-hint")
        self._composer_hint.set_halign(Gtk.Align.CENTER)
        self._composer_hint.set_hexpand(True)
        self._composer_hint.set_justify(Gtk.Justification.CENTER)
        self._composer_hint.set_wrap(True)
        self._composer_hint.set_xalign(0.5)

        self._composer_char_label = Gtk.Label(label="")
        self._composer_char_label.add_css_class("composer-char-count")
        self._composer_char_label.set_halign(Gtk.Align.END)
        self._composer_char_label.set_hexpand(True)
        self._composer_char_label.set_visible(False)
        self._composer_char_label.set_tooltip_text(
            f"Hard safety limit is {COMPOSER_CHAR_LIMIT:,} characters"
        )
        meta_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        meta_row.add_css_class("composer-meta-row")
        meta_row.set_hexpand(True)
        meta_row.append(self._composer_char_label)

        composer_inner.append(self._composer_hint)
        composer_inner.append(shell)
        composer_inner.append(meta_row)

        # Recompute line cap when mapped/resized (compact vs normal max lines).
        self.connect("realize", self._hook_composer_surface_layout)
        self.connect("map", lambda *_: self._apply_composer_height())

        composer_clamp = Adw.Clamp()
        composer_clamp.set_maximum_size(768)
        composer_clamp.set_tightening_threshold(400)
        composer_clamp.set_hexpand(True)
        composer_clamp.set_child(composer_inner)

        composer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        composer.add_css_class("composer-bar")
        composer.set_vexpand(False)
        composer.set_hexpand(True)
        composer.set_valign(Gtk.Align.END)
        composer.set_margin_start(24)
        composer.set_margin_end(24)
        composer.append(composer_clamp)

        # Transcript + composer share one chat surface so the pill floats on it.
        chat_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        chat_column.add_css_class("chat-surface")
        chat_column.set_hexpand(True)
        chat_column.set_vexpand(True)
        chat_column.append(self._transcript_widget)
        chat_column.append(composer)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_hexpand(True)
        outer.set_vexpand(True)
        model_bar.set_vexpand(False)
        outer.append(model_bar)
        outer.append(chat_column)

        # Overlay: model warm-up cover on top of chat chrome
        self._root_overlay = Gtk.Overlay()
        self._root_overlay.set_hexpand(True)
        self._root_overlay.set_vexpand(True)
        self._root_overlay.set_child(outer)
        self._build_load_overlay()
        if self._load_overlay is not None:
            self._root_overlay.add_overlay(self._load_overlay)
        toolbar_view.set_content(self._root_overlay)

        self._history_dirty = True
        GLib.idle_add(self._rebuild_history_list)
        GLib.idle_add(self._refresh_chat_title)

    def _build_history_sidebar(self) -> Gtk.Widget:
        """Docked left rail: Chats header + list + settings footer."""
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        side.add_css_class("chat-sidebar")
        side.set_hexpand(False)
        side.set_vexpand(True)
        side.set_size_request(SIDEBAR_WIDTH, -1)

        # Header: Chats + compact New conversation
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        head.add_css_class("chat-sidebar-header")
        title = Gtk.Label(label="Chats")
        title.add_css_class("chat-sidebar-title")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        title.set_xalign(0)
        head.append(title)

        new_btn = Gtk.Button.new_from_icon_name("document-new-symbolic")
        new_btn.add_css_class("flat")
        new_btn.set_tooltip_text("New conversation")
        new_btn.set_size_request(32, 32)
        new_btn.connect("clicked", lambda *_: self.new_chat())
        head.append(new_btn)
        self._sidebar_new_btn = new_btn
        side.append(head)

        section = Gtk.Label(label="Recent")
        section.add_css_class("chat-sidebar-section")
        section.set_halign(Gtk.Align.START)
        section.set_xalign(0)
        side.append(section)

        self._history_list = Gtk.ListBox()
        self._history_list.add_css_class("navigation-sidebar")
        self._history_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._history_list.set_activate_on_single_click(True)
        self._history_list.connect("row-activated", self._on_history_row_activated)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_child(self._history_list)
        side.append(scroll)

        # Footer: app-level Settings
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        foot.add_css_class("chat-sidebar-footer")
        settings_btn = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
        # Fall back if emblem-system missing
        try:
            display = Gdk.Display.get_default()
            theme = Gtk.IconTheme.get_for_display(display) if display else None
            if theme is not None and not theme.has_icon("emblem-system-symbolic"):
                if theme.has_icon("preferences-system-symbolic"):
                    settings_btn.set_icon_name("preferences-system-symbolic")
        except Exception:  # noqa: BLE001
            settings_btn.set_icon_name("preferences-system-symbolic")
        settings_btn.add_css_class("flat")
        settings_btn.set_tooltip_text("Settings")
        settings_btn.set_size_request(32, 32)
        settings_btn.set_halign(Gtk.Align.START)
        settings_btn.connect("clicked", lambda *_: self.open_settings())
        foot.append(settings_btn)
        self._settings_btn = settings_btn
        side.append(foot)
        return side

    def toggle_sidebar(self, show: bool | None = None) -> None:
        if self._sidebar is None:
            return
        if show is None:
            show = not self._sidebar.get_visible()
        show = bool(show)
        if self._sidebar.get_visible() != show:
            self._sidebar.set_visible(show)
            _save_sidebar_open(show)
        if show:
            self._rebuild_history_list()
        if self._sidebar_btn is not None and self._sidebar_btn.get_active() != show:
            self._sidebar_syncing = True
            self._sidebar_btn.set_active(show)
            self._sidebar_syncing = False

    def open_settings(self) -> None:
        """Minimal settings shell — room for future prefs without scope creep."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Settings",
            body=(
                "Chat data is stored locally on this device under your user data "
                "folder (chickenbutt). More preferences will appear here later."
            ),
        )
        dialog.add_response("close", "Close")
        dialog.add_response("open-data", "Open data folder")
        dialog.set_default_response("close")
        dialog.set_close_response("close")

        def on_response(_d, response: str) -> None:
            if response != "open-data":
                return
            path = Path(GLib.get_user_data_dir()) / "chickenbutt"
            try:
                path.mkdir(parents=True, exist_ok=True)
                Gtk.FileLauncher.new(Gio.File.new_for_path(str(path))).launch(
                    self, None, None, None
                )
            except Exception as exc:  # noqa: BLE001
                # Fallback: xdg-open via Gio.AppInfo
                try:
                    Gio.AppInfo.launch_default_for_uri(
                        path.as_uri(), None
                    )
                except Exception as exc2:  # noqa: BLE001
                    print(f"open data folder: {exc} / {exc2}", flush=True)

        dialog.connect("response", on_response)
        dialog.present()

    def _on_sidebar_toggled(self, btn: Gtk.ToggleButton) -> None:
        if self._sidebar_syncing:
            return
        self.toggle_sidebar(btn.get_active())

    def _mark_history_dirty(self) -> None:
        self._history_dirty = True

    def _refresh_chat_title(self) -> bool:
        """Header subtitle: conversation title when idle."""
        if self._chat_title_label is None:
            return False
        # Don't clobber live status while loading/streaming
        if self._loading_model or self._streaming:
            return False
        title = "New conversation"
        if self._conversation_id:
            try:
                conv = self._store.get_conversation(self._conversation_id)
                if conv and (conv.title or "").strip():
                    title = conv.title.strip()
            except Exception:  # noqa: BLE001
                pass
        if len(title) > 48:
            title = title[:45] + "…"
        self._chat_title_label.set_text(title)
        return False

    def _build_load_overlay(self) -> None:
        veil = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        veil.add_css_class("load-overlay")
        veil.set_hexpand(True)
        veil.set_vexpand(True)
        veil.set_halign(Gtk.Align.FILL)
        veil.set_valign(Gtk.Align.FILL)
        # Block clicks to composer while loading
        veil.set_can_target(True)

        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        center.set_hexpand(True)
        center.set_vexpand(True)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("load-card")
        card.set_halign(Gtk.Align.CENTER)

        spinner = Gtk.Spinner()
        spinner.set_size_request(36, 36)
        spinner.set_halign(Gtk.Align.CENTER)
        spinner.start()
        card.append(spinner)

        self._load_title = Gtk.Label(label="Loading model")
        self._load_title.add_css_class("load-title")
        self._load_title.set_halign(Gtk.Align.CENTER)
        self._load_title.set_margin_top(16)
        card.append(self._load_title)

        self._load_model_label = Gtk.Label(label="")
        self._load_model_label.add_css_class("load-model")
        self._load_model_label.set_halign(Gtk.Align.CENTER)
        self._load_model_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self._load_model_label.set_max_width_chars(36)
        card.append(self._load_model_label)

        self._load_progress = Gtk.ProgressBar()
        self._load_progress.add_css_class("load-progress")
        self._load_progress.set_show_text(False)
        self._load_progress.set_fraction(0.0)
        self._load_progress.pulse()
        card.append(self._load_progress)

        self._load_status = Gtk.Label(label="Connecting to Ollama…")
        self._load_status.add_css_class("load-status")
        self._load_status.set_halign(Gtk.Align.CENTER)
        self._load_status.set_wrap(True)
        self._load_status.set_justify(Gtk.Justification.CENTER)
        self._load_status.set_max_width_chars(40)
        card.append(self._load_status)

        center.append(card)
        veil.append(center)
        veil.set_visible(False)
        self._load_overlay = veil
        self._load_spinner = spinner

    def _hook_composer_surface_layout(self, *_args) -> None:
        """Follow window height changes so compact max-lines kicks in on resize."""
        if getattr(self, "_composer_layout_hooked", False):
            return
        surface = self.get_surface()
        if surface is None:
            return
        surface.connect("layout", lambda *_: self._apply_composer_height())
        self._composer_layout_hooked = True
        self._apply_composer_height()

    def _composer_line_height_px(self) -> int:
        """Approximate one text line in the composer (font + line spacing)."""
        if self.input is None:
            return 22
        try:
            layout = self.input.create_pango_layout("Mg")
            _w, h = layout.get_pixel_size()
            spacing = (
                int(self.input.get_pixels_above_lines())
                + int(self.input.get_pixels_below_lines())
            )
            return max(18, int(h) + spacing)
        except Exception:  # noqa: BLE001
            return 22

    def _composer_max_visible_lines(self) -> int:
        """8 lines normally; 6 on short windows so the composer cannot dominate."""
        try:
            h = int(self.get_height() or 0)
        except Exception:  # noqa: BLE001
            h = 0
        if h <= 0:
            try:
                h = int(self.get_default_size()[1] or DEFAULT_HEIGHT)
            except Exception:  # noqa: BLE001
                h = DEFAULT_HEIGHT
        if h <= COMPOSER_COMPACT_WINDOW_HEIGHT:
            return COMPOSER_COMPACT_MAX_LINES
        return COMPOSER_MAX_LINES

    def _composer_content_height_px(self) -> int:
        """Natural height of the text view at its current width (wrapped lines)."""
        if self.input is None:
            return 36
        w = int(self.input.get_width() or 0)
        if w <= 1 and self._input_scroll is not None:
            w = int(self._input_scroll.get_width() or 0)
        if w <= 1:
            w = 400
        try:
            _mn, nat, _mn_b, _nat_b = self.input.measure(Gtk.Orientation.VERTICAL, w)
            return max(1, int(nat))
        except Exception:  # noqa: BLE001
            return 36

    def _apply_composer_height(self, *_args) -> None:
        """Cap visible composer height; content may be longer and scrolls inside."""
        if self._input_scroll is None or self.input is None:
            return
        line = self._composer_line_height_px()
        pad = int(self.input.get_top_margin()) + int(self.input.get_bottom_margin())
        # Match circular send button (~36px) so a one-line shell looks balanced.
        min_h = max(36, pad + line * COMPOSER_MIN_LINES)
        max_h = max(min_h, pad + line * self._composer_max_visible_lines())
        content_h = self._composer_content_height_px()
        target = max(min_h, min(content_h, max_h))
        needs_scroll = content_h > max_h
        # Only enable a vertical scrollbar once we hit the visible-line cap.
        # AUTOMATIC while short reserves scrollbar chrome and un-centers the send button.
        self._input_scroll.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC if needs_scroll else Gtk.PolicyType.NEVER,
        )
        self._input_scroll.set_min_content_height(target)
        self._input_scroll.set_max_content_height(max_h)
        self._input_scroll.set_size_request(-1, target)
        parent = self._input_scroll.get_parent()
        if parent is not None:
            parent.set_size_request(-1, target)
        self._sync_composer_action_valign(content_h=content_h, min_h=min_h)

    def _sync_composer_action_valign(
        self, content_h: int | None = None, min_h: int | None = None
    ) -> None:
        """Center send/stop on one line; pin to bottom once the composer grows."""
        if content_h is None:
            content_h = self._composer_content_height_px()
        if min_h is None and self._input_scroll is not None:
            min_h = int(self._input_scroll.get_min_content_height() or 36)
        if min_h is None:
            min_h = 36
        multi = content_h > min_h + 6
        align = Gtk.Align.END if multi else Gtk.Align.CENTER
        for btn in (self.send_btn, self.stop_btn):
            if btn is not None:
                btn.set_valign(align)

    def _update_composer_char_counter(self, n: int) -> None:
        lab = self._composer_char_label
        if lab is None:
            return
        show = n >= int(COMPOSER_CHAR_LIMIT * COMPOSER_COUNTER_SHOW_RATIO)
        lab.set_visible(show)
        if not show:
            return
        lab.set_text(f"{n:,} / {COMPOSER_CHAR_LIMIT:,}")
        if n >= COMPOSER_CHAR_LIMIT:
            lab.add_css_class("warning")
            lab.set_tooltip_text("Character safety limit reached")
        else:
            lab.remove_css_class("warning")
            lab.set_tooltip_text(
                f"Hard safety limit is {COMPOSER_CHAR_LIMIT:,} characters"
            )

    def _composer_hint_should_show(self) -> bool:
        """Show keyboard hint only before the conversation has real turns."""
        for m in self._messages:
            if _is_ephemeral_greeting(m.get("role", ""), m.get("content", "")):
                continue
            return False
        return True

    def _sync_composer_hint(self) -> None:
        """Center hint above the pill; fade out once the chat starts."""
        hint = self._composer_hint
        if hint is None:
            return
        want = self._composer_hint_should_show()
        if self._composer_hint_fade_id:
            try:
                GLib.source_remove(self._composer_hint_fade_id)
            except Exception:  # noqa: BLE001
                pass
            self._composer_hint_fade_id = 0
        if want:
            hint.remove_css_class("faded")
            hint.set_visible(True)
            return
        if not hint.get_visible() and hint.has_css_class("faded"):
            return
        hint.set_visible(True)
        hint.add_css_class("faded")

        def _hide() -> bool:
            self._composer_hint_fade_id = 0
            if self._composer_hint is not None and not self._composer_hint_should_show():
                self._composer_hint.set_visible(False)
            return False

        self._composer_hint_fade_id = GLib.timeout_add(300, _hide)

    def _on_composer_insert_text(
        self, buf: Gtk.TextBuffer, _location, text: str, _length: int
    ) -> None:
        """Enforce the hard character safety cap at insert time (paste-friendly)."""
        if self._composer_truncating or not text:
            return
        current = buf.get_char_count()
        remaining = COMPOSER_CHAR_LIMIT - current
        if remaining <= 0:
            buf.stop_emission_by_name("insert-text")
            self._update_composer_char_counter(current)
            return
        # text may be str; clamp oversized pastes instead of rejecting entirely
        if len(text) > remaining:
            buf.stop_emission_by_name("insert-text")
            self._composer_truncating = True
            try:
                buf.insert(_location, text[:remaining])
            finally:
                self._composer_truncating = False

    def _on_buffer_changed(self, buf: Gtk.TextBuffer) -> None:
        if self._composer_truncating:
            return
        n = buf.get_char_count()
        if n > COMPOSER_CHAR_LIMIT:
            self._composer_truncating = True
            try:
                start = buf.get_iter_at_offset(COMPOSER_CHAR_LIMIT)
                end = buf.get_end_iter()
                buf.delete(start, end)
                n = COMPOSER_CHAR_LIMIT
            finally:
                self._composer_truncating = False
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        if self._placeholder is not None:
            self._placeholder.set_visible(len(text) == 0)
        self._update_composer_char_counter(n)
        # Natural height can change as lines wrap; keep min/max in sync after font ready.
        self._apply_composer_height()
        # Height allocation updates next frame — re-check button valign after layout.
        GLib.idle_add(self._sync_composer_action_valign)

    def _brand_icon_path(self, *, for_dark_ui: bool | None = None) -> Path:
        """Empty/greeting mark: tight icon SVGs (not 1920x1080 logos).

        light-icon = white chick for dark UI; dark-icon = black chick for light UI.
        """
        if for_dark_ui is None:
            try:
                for_dark_ui = bool(Adw.StyleManager.get_default().get_dark())
            except Exception:  # noqa: BLE001
                for_dark_ui = True
        name = (
            "chickenbutt-light-icon.svg"
            if for_dark_ui
            else "chickenbutt-dark-icon.svg"
        )
        return Path(__file__).resolve().parent / "icons" / name

    def _make_empty_brand_icon(self) -> Gtk.Widget:
        path = self._brand_icon_path()
        try:
            pic = Gtk.Picture.new_for_filename(str(path))
            pic.set_can_shrink(True)
            pic.set_content_fit(Gtk.ContentFit.CONTAIN)
            pic.set_size_request(64, 64)
            pic.set_halign(Gtk.Align.CENTER)
            pic.add_css_class("empty-icon")
            self._empty_icon = pic
            return pic
        except Exception:  # noqa: BLE001
            fallback = Gtk.Label(label="✦")
            fallback.add_css_class("empty-icon")
            fallback.set_halign(Gtk.Align.CENTER)
            self._empty_icon = fallback
            return fallback

    def _sync_empty_brand_icon(self, *_args) -> None:
        """Swap empty-state mark when the system color scheme changes."""
        pic = getattr(self, "_empty_icon", None)
        if pic is None or not isinstance(pic, Gtk.Picture):
            return
        path = self._brand_icon_path()
        try:
            pic.set_filename(str(path))
        except Exception:  # noqa: BLE001
            pass

    def _show_empty_state(self) -> None:
        if self.chat_box is None:
            return
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class("empty-state")
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_hexpand(True)
        # No vexpand: natural height must not push the window past the screen
        box.set_vexpand(False)
        box.set_margin_top(48)
        box.set_margin_bottom(48)

        icon = self._make_empty_brand_icon()

        title = Gtk.Label(label="Start a conversation")
        title.add_css_class("empty-title")
        title.set_halign(Gtk.Align.CENTER)
        self._empty_title = title

        sub = Gtk.Label(
            label=(
                "Messages stream from your local Ollama models.\n"
                "Need a model?\n"
                "Type in the box: ollama pull <model-name>"
            )
        )
        sub.add_css_class("empty-sub")
        sub.add_css_class("dim-label")
        sub.set_justify(Gtk.Justification.CENTER)
        sub.set_halign(Gtk.Align.CENTER)
        sub.set_wrap(True)
        self._empty_sub = sub

        box.append(icon)
        box.append(title)
        box.append(sub)
        self.chat_box.set_valign(Gtk.Align.START)
        self.chat_box.append(box)
        self._empty_box = box

    def toggle(self) -> None:
        if self.is_visible():
            self.set_visible(False)
        else:
            self.present()
            self.input.grab_focus()

    def hide_to_tray(self) -> None:
        """Hide window (same as close button → tray)."""
        self.set_visible(False)

    def toggle_maximize(self) -> None:
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()

    def clear_chat(self) -> None:
        if self._streaming:
            self._request_stop()
        self._messages.clear()
        self._greeted_models.clear()
        self._native_rows.clear()
        # Keep one active row; wipe messages so restart is empty
        try:
            if self._conversation_id:
                self._store.clear_messages(self._conversation_id)
            else:
                conv = self._store.create_conversation(model=self._model)
                self._conversation_id = conv.id
        except Exception as exc:  # noqa: BLE001
            print(f"clear_chat persist: {exc}", flush=True)
        # Empty chats are hidden from Recent
        self._mark_history_dirty()
        self._rebuild_history_list()
        self._render_empty_transcript()
        self._set_status(self._model or "Ready")
        # Re-show ephemeral greeting if a model is already warm
        if self._model and not self._loading_model and not self._load_failed:
            self._show_ephemeral_greeting()
        self._refresh_chat_title()
        self._sync_composer_hint()

    def _active_chat_is_empty(self) -> bool:
        """True when there is nothing meaningful to abandon (no saved messages)."""
        if self._messages:
            return False
        if not self._conversation_id:
            return True
        try:
            return self._store.is_empty(self._conversation_id)
        except Exception:  # noqa: BLE001
            return not self._messages

    def new_chat(self) -> None:
        """Create and activate a new empty conversation (multi-chat).

        If the active chat is already empty, do not create another DB row —
        just focus the composer.
        """
        if self._streaming:
            self._invalidate_active_stream()
        if self._loading_model:
            return

        # Already on a blank slate — avoid empty-chat proliferation
        if self._active_chat_is_empty():
            if self._model and not self._load_failed and not self._messages:
                self._show_ephemeral_greeting()
            if self.input is not None:
                try:
                    self.input.grab_focus()
                except Exception:  # noqa: BLE001
                    pass
            return

        # Drop other abandoned empty rows before creating a new one
        try:
            self._store.prune_empty_conversations(keep_id=None)
        except Exception as exc:  # noqa: BLE001
            print(f"prune_empty: {exc}", flush=True)

        try:
            conv = self._store.create_conversation(model=self._model)
            self._conversation_id = conv.id
        except Exception as exc:  # noqa: BLE001
            print(f"new_chat: {exc}", flush=True)
            return
        self._messages.clear()
        self._greeted_models.clear()
        self._native_rows.clear()
        self._history_restored = False
        self._render_empty_transcript()
        self._set_status(self._model or "Ready")
        if self._model and not self._load_failed:
            self._show_ephemeral_greeting()
        self._mark_history_dirty()
        self._rebuild_history_list()
        self._refresh_chat_title()
        self._sync_composer_hint()
        if self.input is not None:
            try:
                self.input.grab_focus()
            except Exception:  # noqa: BLE001
                pass
        print(f"New chat {conv.id[:12]}…", flush=True)

    def _render_empty_transcript(self) -> None:
        if self._transcript_mode == "webkit" and self._web is not None:
            self._web.reset([])
        elif self.chat_box is not None:
            while child := self.chat_box.get_first_child():
                self.chat_box.remove(child)
            self._show_empty_state()

    def _rebuild_history_list(self) -> bool:
        """Refresh sidebar rows only when history is dirty (or empty)."""
        if self._history_list is None:
            return False
        if not self._history_dirty and self._history_list.get_first_child() is not None:
            self._select_active_history_row()
            return False
        # GTK4 ListBox: remove children
        child = self._history_list.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._history_list.remove(child)
            child = nxt
        try:
            convs = self._store.list_conversations(limit=40)
        except Exception as exc:  # noqa: BLE001
            print(f"list_conversations: {exc}", flush=True)
            convs = []
        if not convs:
            empty = Gtk.Label(label="No chats yet")
            empty.add_css_class("dim-label")
            empty.set_margin_top(12)
            empty.set_margin_bottom(12)
            placeholder = Gtk.ListBoxRow()
            placeholder.set_child(empty)
            placeholder.set_sensitive(False)
            self._history_list.append(placeholder)
            self._history_dirty = False
            return False
        active_row = None
        for conv in convs:
            title = (conv.title or "").strip() or "New conversation"
            if len(title) > 36:
                title = title[:33] + "…"
            row = Gtk.ListBoxRow()
            row.set_name(conv.id)

            outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            outer.set_margin_top(6)
            outer.set_margin_bottom(6)
            outer.set_margin_start(8)
            outer.set_margin_end(4)

            text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text_col.set_hexpand(True)
            lab = Gtk.Label(label=title)
            lab.add_css_class("chat-sidebar-row-title")
            lab.set_halign(Gtk.Align.START)
            lab.set_xalign(0)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            lab.set_max_width_chars(18)
            if conv.id == self._conversation_id:
                lab.add_css_class("chat-sidebar-row-active")
                active_row = row
            text_col.append(lab)
            if conv.model:
                sub = Gtk.Label(label=conv.model)
                sub.add_css_class("chat-sidebar-row-meta")
                sub.set_halign(Gtk.Align.START)
                sub.set_xalign(0)
                sub.set_ellipsize(Pango.EllipsizeMode.END)
                sub.set_max_width_chars(18)
                text_col.append(sub)
            outer.append(text_col)

            # Single overflow menu — less noise than separate export/delete icons
            cid = conv.id
            more_btn = Gtk.MenuButton()
            more_btn.set_icon_name("view-more-symbolic")
            more_btn.add_css_class("flat")
            more_btn.add_css_class("chat-sidebar-row-actions")
            more_btn.set_tooltip_text("Chat actions")
            more_btn.set_has_frame(False)
            more_btn.set_can_focus(False)
            more_btn.set_valign(Gtk.Align.CENTER)
            more_btn.set_popover(self._make_chat_actions_popover(cid))
            outer.append(more_btn)

            row.set_child(outer)
            self._history_list.append(row)
        if active_row is not None:
            self._history_list.select_row(active_row)
        self._history_dirty = False
        self._refresh_chat_title()
        return False

    def _select_active_history_row(self) -> None:
        if self._history_list is None or not self._conversation_id:
            return
        row = self._history_list.get_first_child()
        while row is not None:
            if isinstance(row, Gtk.ListBoxRow) and row.get_name() == self._conversation_id:
                self._history_list.select_row(row)
                return
            row = row.get_next_sibling()

    def _on_history_row_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        cid = row.get_name()
        if not cid:
            return
        self.switch_conversation(cid)

    def _make_chat_actions_popover(self, conversation_id: str) -> Gtk.Popover:
        """Overflow: icon actions — Markdown, JSON, Delete (tooltips carry meaning)."""
        pop = Gtk.Popover()
        # Horizontal strip: [MD] [JSON] [trash]
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)

        def add_icon(icon_name: str, tooltip: str, handler, *, destructive: bool = False) -> None:
            # Prefer symbolic; fall back to full mime icons (text-markdown / application-json)
            name = icon_name
            try:
                display = self.get_display()
                theme = Gtk.IconTheme.get_for_display(display) if display else None
                if theme is not None and not theme.has_icon(name):
                    # try -symbolic suffix or base name without it
                    if name.endswith("-symbolic"):
                        alt = name[: -len("-symbolic")]
                        if theme.has_icon(alt):
                            name = alt
                    elif theme.has_icon(name + "-symbolic"):
                        name = name + "-symbolic"
            except Exception:  # noqa: BLE001
                pass
            btn = Gtk.Button.new_from_icon_name(name)
            btn.add_css_class("flat")
            if destructive:
                btn.add_css_class("destructive-action")
            btn.set_has_frame(False)
            btn.set_tooltip_text(tooltip)
            btn.set_size_request(36, 36)
            btn.connect("clicked", lambda _b: (pop.popdown(), handler()))
            box.append(btn)

        # MIME icons distinguish formats; trash is standard Adwaita symbolic
        add_icon(
            "text-markdown",
            "Export Markdown",
            lambda: self.export_conversation(conversation_id, "md"),
        )
        add_icon(
            "application-json",
            "Export JSON",
            lambda: self.export_conversation(conversation_id, "json"),
        )
        add_icon(
            "user-trash-symbolic",
            "Delete chat",
            lambda: self._confirm_delete_conversation(conversation_id),
            destructive=True,
        )
        pop.set_child(box)
        return pop

    def _conversation_display_title(self, conversation_id: str) -> str:
        """Best human title for dialogs / export names."""
        try:
            conv = self._store.get_conversation(conversation_id)
            if conv and (conv.title or "").strip():
                return conv.title.strip()
            for m in self._store.list_messages(conversation_id):
                if m.role == "user" and (m.content or "").strip():
                    return m.content.strip().splitlines()[0][:80]
        except Exception:  # noqa: BLE001
            pass
        if conversation_id == self._conversation_id:
            for m in self._messages:
                if m.get("role") == "user" and (m.get("content") or "").strip():
                    return str(m["content"]).strip().splitlines()[0][:80]
        return "this chat"

    def _safe_export_basename(self, conversation_id: str) -> str:
        title = self._conversation_display_title(conversation_id)
        if title == "this chat":
            title = "chat"
        # Filesystem-friendly
        safe = "".join(c if c.isalnum() or c in " -_" else "-" for c in title)
        safe = "-".join(safe.split())[:48].strip("-") or "chat"
        return f"chickenbutt-{safe}"

    def export_conversation(self, conversation_id: str, fmt: str = "md") -> None:
        """Save conversation as Markdown or JSON via file dialog."""
        fmt = (fmt or "md").lower().strip(".")
        if fmt not in ("md", "markdown", "json"):
            fmt = "md"
        if fmt == "markdown":
            fmt = "md"

        if fmt == "json":
            payload = self._store.export_dict(conversation_id)
            if payload is None:
                print("export: conversation not found", flush=True)
                return
            body = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
            ext = "json"
            mime = "application/json"
        else:
            body = self._store.export_markdown(conversation_id)
            if body is None:
                print("export: conversation not found", flush=True)
                return
            ext = "md"
            mime = "text/markdown"

        basename = f"{self._safe_export_basename(conversation_id)}.{ext}"
        dialog = Gtk.FileDialog()
        dialog.set_title("Export chat")
        dialog.set_initial_name(basename)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filt = Gtk.FileFilter()
        if ext == "json":
            filt.set_name("JSON")
            filt.add_pattern("*.json")
            filt.add_mime_type(mime)
        else:
            filt.set_name("Markdown")
            filt.add_pattern("*.md")
            filt.add_mime_type(mime)
        filters.append(filt)
        dialog.set_filters(filters)
        dialog.set_default_filter(filt)

        def on_save(_dlg, result) -> None:
            try:
                file = dialog.save_finish(result)
            except GLib.Error as exc:
                # Dismissed / cancelled
                if exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED):
                    return
                print(f"export dialog: {exc}", flush=True)
                return
            if file is None:
                return
            path = file.get_path()
            if not path:
                print("export: no path", flush=True)
                return
            try:
                Path(path).write_text(body, encoding="utf-8")
                print(f"Exported {fmt} → {path}", flush=True)
            except OSError as exc:
                print(f"export write failed: {exc}", flush=True)
                err = Adw.MessageDialog(
                    transient_for=self,
                    heading="Export failed",
                    body=str(exc),
                )
                err.add_response("ok", "OK")
                err.present()

        dialog.save(self, None, on_save)

    def _confirm_delete_conversation(self, conversation_id: str) -> None:
        title = self._conversation_display_title(conversation_id)
        if len(title) > 60:
            title = title[:57] + "…"
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Delete chat?",
            body=f'"{title}" will be permanently removed from this device.',
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_d, response: str) -> None:
            if response == "delete":
                self.delete_conversation(conversation_id)

        dialog.connect("response", on_response)
        dialog.present()

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a chat from SQLite and UI; switch away if it was active."""
        if not conversation_id:
            return
        if self._streaming and conversation_id == self._conversation_id:
            self._invalidate_active_stream()
        was_active = conversation_id == self._conversation_id
        try:
            self._store.delete_conversation(conversation_id)
        except Exception as exc:  # noqa: BLE001
            print(f"delete_conversation: {exc}", flush=True)
            return
        self._mark_history_dirty()
        if was_active:
            # Switch to next remaining chat, or create empty
            nxt = self._store.get_active_conversation()
            if nxt is not None:
                # Force reload even if id was reassigned in meta
                self._conversation_id = None
                self.switch_conversation(nxt.id)
            else:
                self.new_chat()
        else:
            self._rebuild_history_list()
        print(f"Deleted chat {conversation_id[:12]}…", flush=True)

    def switch_conversation(self, conversation_id: str) -> None:
        """Activate another conversation and replay its transcript."""
        if not conversation_id or conversation_id == self._conversation_id:
            return
        if self._streaming:
            self._invalidate_active_stream()
        if self._loading_model:
            return
        # Leaving an empty draft — drop it so Recent stays clean
        prev = self._conversation_id
        if prev and prev != conversation_id:
            try:
                if self._store.is_empty(prev):
                    self._store.delete_conversation(prev)
                    self._mark_history_dirty()
            except Exception as exc:  # noqa: BLE001
                print(f"prune empty on switch: {exc}", flush=True)
        conv = self._store.get_conversation(conversation_id)
        if conv is None:
            print(f"switch_conversation: missing {conversation_id}", flush=True)
            return
        try:
            self._store.set_active(conversation_id)
        except Exception as exc:  # noqa: BLE001
            print(f"set_active: {exc}", flush=True)
        self._conversation_id = conversation_id
        self._greeted_models.clear()
        self._native_rows.clear()
        # Load messages (filter legacy greeting)
        try:
            stored = self._store.list_messages(conversation_id)
        except Exception as exc:  # noqa: BLE001
            print(f"switch load messages: {exc}", flush=True)
            stored = []
        real = [
            m
            for m in stored
            if not _is_ephemeral_greeting(m.role, m.content)
        ]
        self._messages = [
            {"id": m.id, "role": m.role, "content": m.content} for m in real
        ]
        self._history_restored = bool(real)
        payload = [
            {"id": m.id, "role": m.role, "content": m.content} for m in real
        ]
        if real:
            self._apply_restored_transcript(payload)
        else:
            self._render_empty_transcript()
            if self._model and not self._load_failed:
                self._show_ephemeral_greeting()
        self._sync_composer_hint()
        # Restore per-conversation model when available
        if conv.model:
            _save_last_model(conv.model)
            self._select_model_name(conv.model, warm=True, greet=not real)
        else:
            self._set_status(self._model or "Ready")
        self._mark_history_dirty()
        self._rebuild_history_list()
        self._refresh_chat_title()
        print(
            f"Switched to {conversation_id[:12]}… "
            f"({len(real)} messages)",
            flush=True,
        )

    def _select_model_name(
        self, name: str, *, warm: bool = False, greet: bool = False
    ) -> None:
        """Select a model in the dropdown; optionally warm it."""
        if not name or self.model_combo is None:
            return
        model = self.model_combo.get_model()
        if model is None:
            self._model = name
            if warm:
                self._begin_model_load(name, greet=greet)
            return
        n = model.get_n_items()
        found = -1
        for i in range(n):
            item = model.get_item(i)
            if item is None:
                continue
            s = item.get_string()
            if s == name or s.split(":")[0] == name.split(":")[0]:
                found = i
                if s == name:
                    break
        self._suppress_model_select = True
        if found >= 0:
            self.model_combo.set_selected(found)
            item = model.get_item(found)
            self._model = item.get_string() if item else name
        else:
            self._model = name
        self._suppress_model_select = False
        if warm and self._model and not self._loading_model:
            self._begin_model_load(
                self._model, greet=bool(greet) and not self._messages
            )

    def _on_web_intent(self, payload: dict) -> bool:
        """Handle intents from the WebKit page (copy, links, message actions…)."""
        typ = payload.get("type")
        if typ == "copy_text":
            text = payload.get("text") or ""
            display = Gdk.Display.get_default()
            if display is not None and text:
                display.get_clipboard().set(text)
        elif typ == "open_link":
            url = payload.get("url") or ""
            if url:
                try:
                    Gtk.show_uri(self, url, Gdk.CURRENT_TIME)
                except Exception:
                    try:
                        Gtk.UriLauncher.new(url).launch(self, None, None, None)
                    except Exception as exc:  # noqa: BLE001
                        print(f"open_link: {exc}", flush=True)
        elif typ == "ready":
            pass
        elif typ == "regenerate":
            self._regenerate_message(str(payload.get("id") or ""))
        elif typ == "continue":
            self._continue_message(str(payload.get("id") or ""))
        elif typ == "delete_message":
            self._delete_message(str(payload.get("id") or ""))
        elif typ == "edit_resend":
            self._edit_resend_message(
                str(payload.get("id") or ""),
                str(payload.get("text") or ""),
            )
        return False

    def _next_msg_id(self, prefix: str) -> str:
        self._msg_counter += 1
        return f"{prefix}-{self._msg_counter}-{uuid.uuid4().hex[:6]}"

    def _ensure_conversation(self) -> str:
        if self._conversation_id:
            return self._conversation_id
        conv = self._store.ensure_active(model=self._model)
        self._conversation_id = conv.id
        return conv.id

    def _persist_message(self, role: str, content: str, message_id: str | None = None) -> None:
        try:
            cid = self._ensure_conversation()
            self._store.append_message(
                cid,
                role=role,
                content=content,
                message_id=message_id,
            )
            # First user message sets title — sidebar + header need refresh
            if role == "user":
                self._mark_history_dirty()
                GLib.idle_add(self._refresh_chat_title)
        except Exception as exc:  # noqa: BLE001
            print(f"persist message failed: {exc}", flush=True)

    def _restore_history(self) -> None:
        """Load most recent / active conversation into memory + transcript."""
        try:
            conv = self._store.get_active_conversation()
            if conv is None:
                conv = self._store.create_conversation(model=self._model)
            self._conversation_id = conv.id
            # Drop abandoned empty chats (keep the active row even if empty)
            try:
                n = self._store.prune_empty_conversations(keep_id=conv.id)
                if n:
                    print(f"Pruned {n} empty chat(s)", flush=True)
                    self._mark_history_dirty()
            except Exception as exc:  # noqa: BLE001
                print(f"prune on restore: {exc}", flush=True)
            stored = self._store.list_messages(conv.id)
            # Drop legacy greeting rows (never model context, never chat bubbles)
            real = [
                m
                for m in stored
                if not _is_ephemeral_greeting(m.role, m.content)
            ]
            legacy = [m for m in stored if _is_ephemeral_greeting(m.role, m.content)]
            for m in legacy:
                try:
                    self._store.delete_message(m.id)
                except Exception:  # noqa: BLE001
                    pass
            if legacy:
                try:
                    self._store.touch(conv.id)
                except Exception:  # noqa: BLE001
                    pass
            if not real:
                self._history_restored = False
                self._messages = []
                return
            payload = [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                }
                for m in real
            ]
            self._messages = [
                {"id": m.id, "role": m.role, "content": m.content} for m in real
            ]
            self._history_restored = True
            if conv.model:
                _save_last_model(conv.model)
            self._apply_restored_transcript(payload)
            self._sync_composer_hint()
            print(
                f"Restored conversation {conv.id[:12]}… "
                f"({len(real)} messages)",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"restore history failed: {exc}", flush=True)
            self._history_restored = False

    def _apply_restored_transcript(self, messages: list[dict[str, str]]) -> None:
        if self._transcript_mode == "webkit" and self._web is not None:
            # WebView may not be ready yet; reset queues until load finishes
            self._web.reset(messages)
            return
        if self.chat_box is None:
            return
        while child := self.chat_box.get_first_child():
            self.chat_box.remove(child)
        self._empty_box = None
        self._native_rows.clear()
        if not messages:
            self._show_empty_state()
            return
        for m in messages:
            role = m.get("role") or "assistant"
            content = m.get("content") or ""
            mid = m.get("id") or self._next_msg_id(role[:4])
            if role == "user":
                self._append_message("user", content, message_id=mid)
            else:
                self._append_message(
                    "assistant", content, markdown=True, message_id=mid
                )

    def _find_message_index(self, message_id: str) -> int:
        for i, m in enumerate(self._messages):
            if m.get("id") == message_id:
                return i
        return -1

    def _api_messages(self, messages: list[dict] | None = None) -> list[dict[str, str]]:
        src = messages if messages is not None else self._messages
        return [
            {"role": m["role"], "content": m["content"]}
            for m in src
            if m.get("role") in ("user", "assistant") and m.get("content") is not None
        ]

    def _clipboard_set(self, text: str) -> None:
        display = Gdk.Display.get_default()
        if display is not None and text is not None:
            display.get_clipboard().set(text)

    def _delete_message(self, message_id: str) -> None:
        if not message_id or self._streaming or self._loading_model:
            return
        idx = self._find_message_index(message_id)
        if idx < 0:
            return
        # Drop this message and everything after (keeps transcript coherent)
        dropped = self._messages[idx:]
        self._messages = self._messages[:idx]
        for m in dropped:
            mid = m.get("id")
            if not mid:
                continue
            try:
                self._store.delete_message(mid, conversation_id=self._conversation_id)
            except Exception as exc:  # noqa: BLE001
                print(f"delete persist: {exc}", flush=True)
            if self._transcript_mode == "webkit" and self._web is not None:
                self._web.post({"type": "message_removed", "id": mid})
            else:
                self._native_remove_message(mid)
        if not self._messages:
            if self._transcript_mode == "webkit" and self._web is not None:
                self._web.reset([])
            elif self.chat_box is not None:
                while child := self.chat_box.get_first_child():
                    self.chat_box.remove(child)
                self._native_rows.clear()
                self._show_empty_state()

    def _drop_messages_from(self, idx: int, *, keep_ui_id: str | None = None) -> None:
        """Remove messages[idx:] from memory, DB, and transcript UI."""
        if idx < 0 or idx >= len(self._messages):
            return
        dropped = self._messages[idx:]
        self._messages = self._messages[:idx]
        for m in dropped:
            mid = m.get("id")
            if not mid:
                continue
            try:
                self._store.delete_message(mid, conversation_id=self._conversation_id)
            except Exception as exc:  # noqa: BLE001
                print(f"drop persist: {exc}", flush=True)
            if keep_ui_id and mid == keep_ui_id:
                continue
            if self._transcript_mode == "webkit" and self._web is not None:
                self._web.post({"type": "message_removed", "id": mid})
            else:
                self._native_remove_message(mid)

    def _regenerate_message(self, message_id: str) -> None:
        if not message_id or self._streaming or self._loading_model or not self._model:
            return
        idx = self._find_message_index(message_id)
        if idx < 0:
            return
        role = self._messages[idx].get("role")
        if role == "user":
            # Re-run from this user turn: drop following replies, stream new assistant
            self._drop_messages_from(idx + 1)
            prefix = list(self._messages)
            self._start_assistant_stream(
                mode="new",
                api_messages=self._api_messages(prefix),
            )
            return
        if role != "assistant":
            return
        # Replace this assistant reply; drop any later turns
        dropped_tail = self._messages[idx + 1 :]
        for m in dropped_tail:
            mid = m.get("id")
            if not mid:
                continue
            try:
                self._store.delete_message(mid, conversation_id=self._conversation_id)
            except Exception as exc:  # noqa: BLE001
                print(f"regen tail delete: {exc}", flush=True)
            if self._transcript_mode == "webkit" and self._web is not None:
                self._web.post({"type": "message_removed", "id": mid})
            else:
                self._native_remove_message(mid)
        self._messages = self._messages[:idx]
        try:
            self._store.delete_message(message_id, conversation_id=self._conversation_id)
        except Exception as exc:  # noqa: BLE001
            print(f"regen delete: {exc}", flush=True)
        prefix = list(self._messages)
        self._start_assistant_stream(
            mode="replace",
            assistant_id=message_id,
            api_messages=self._api_messages(prefix),
        )

    def _edit_resend_message(self, message_id: str, text: str) -> None:
        """Edit a user prompt, drop later turns, resubmit to the model."""
        text = (text or "").strip()
        if (
            not message_id
            or not text
            or self._streaming
            or self._loading_model
            or not self._model
        ):
            return
        idx = self._find_message_index(message_id)
        if idx < 0 or self._messages[idx].get("role") != "user":
            return
        self._messages[idx]["content"] = text
        try:
            self._store.update_message(message_id, text)
        except Exception as exc:  # noqa: BLE001
            print(f"edit_resend persist: {exc}", flush=True)
        # Drop everything after this user message
        self._drop_messages_from(idx + 1)
        # Sync bubble text (WebKit edit UI already set it; still push for consistency)
        if self._transcript_mode == "webkit" and self._web is not None:
            self._web.post(
                {
                    "type": "message_added",
                    "id": message_id,
                    "role": "user",
                    "text": text,
                    "streaming": False,
                }
            )
        else:
            self._native_remove_message(message_id)
            self._append_message("user", text, message_id=message_id)
        prefix = list(self._messages)
        self._start_assistant_stream(
            mode="new",
            api_messages=self._api_messages(prefix),
        )

    def _continue_message(self, message_id: str) -> None:
        if not message_id or self._streaming or self._loading_model or not self._model:
            return
        idx = self._find_message_index(message_id)
        if idx < 0 or self._messages[idx].get("role") != "assistant":
            return
        # Only allow continue on the last assistant message (stable ordering)
        if idx != len(self._messages) - 1:
            print("continue: only the latest assistant message", flush=True)
            return
        seed = self._messages[idx].get("content") or ""
        api = self._api_messages(self._messages[: idx + 1])
        api.append(
            {
                "role": "user",
                "content": (
                    "Continue your previous response without repeating "
                    "what you already wrote."
                ),
            }
        )
        self._start_assistant_stream(
            mode="continue",
            assistant_id=message_id,
            seed_text=seed,
            api_messages=api,
        )

    def _set_status(self, text: str) -> None:
        if self._status_label is None:
            return
        # Transient states use the subtitle; idle falls back to chat title
        if self._loading_model or self._streaming or text in (
            "Load failed",
            "Connecting…",
            "Thinking…",
        ):
            self._status_label.set_text(text)
        elif text and text not in ("Ready",) and self._model and text == self._model:
            # Model name — prefer conversation title when we have one
            self._refresh_chat_title()
        else:
            self._refresh_chat_title()

    def _on_input_key(self, _controller, keyval, _keycode, state) -> bool:
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if state & Gdk.ModifierType.SHIFT_MASK:
                return False
            self._send()
            return True
        return False

    def _on_model_selected(self, *_args) -> None:
        if self._suppress_model_select:
            return
        item = self.model_combo.get_selected_item()
        if item is None:
            return
        name = item.get_string()
        if not name or "Loading" in name or "No models" in name:
            return
        # Ignore truncated Ollama errors stuffed into the dropdown
        if name.startswith("Cannot reach") or name.startswith("Error"):
            return
        # Same model: only reload after a failed attempt (retry)
        if name == self._model and not self._loading_model and not self._load_failed:
            return
        self._model = name
        self._set_status(name)
        self._begin_model_load(name, greet=not self._messages)

    def _refresh_models(self) -> bool:
        if self._loading_model:
            return False
        # Probe without a blocking modal — keep transcript visible
        self._apply_health(checking_state())
        self._set_status("Checking Ollama…")
        self._set_load_controls_sensitive(False)
        if self._refresh_btn is not None:
            self._refresh_btn.set_sensitive(False)

        def work():
            result = probe_ollama(self.client)
            GLib.idle_add(self._on_ollama_probe, result)

        threading.Thread(target=work, daemon=True).start()
        return False

    def _on_ollama_probe(self, result) -> bool:
        """Apply probe result: health banner + model list / warm-up."""
        self._apply_health(result.state)
        models = list(result.models or [])
        if result.state.kind == HealthKind.OK and models:
            self._load_failed = False
            strings = models
            model_list = Gtk.StringList.new(strings)
            self._suppress_model_select = True
            self.model_combo.set_model(model_list)
            preferred = self._preferred_model()
            idx = _pick_startup_model(models, preferred)
            self.model_combo.set_selected(idx)
            chosen = models[idx]
            self._model = chosen
            self.send_btn.set_sensitive(False)
            self._set_status(f"Loading {chosen}…")
            self._suppress_model_select = False
            self._begin_model_load(chosen, greet=not self._messages)
            return False

        # Unhealthy or no models — do not block the transcript with a modal
        self._hide_load_overlay()
        self._load_failed = True
        self._model = None
        if result.state.kind == HealthKind.NO_MODELS:
            placeholder = ["No models installed"]
        elif result.state.kind in (
            HealthKind.NOT_RUNNING,
            HealthKind.NOT_INSTALLED,
        ):
            placeholder = ["Ollama unavailable"]
        else:
            placeholder = [(result.state.title or "Ollama error")[:80]]
        self._suppress_model_select = True
        self.model_combo.set_model(Gtk.StringList.new(placeholder))
        self._suppress_model_select = False
        self.send_btn.set_sensitive(False)
        self._set_status(result.state.title)
        # Refresh + picker enabled for recovery; send stays off
        self._set_load_controls_sensitive(True)
        if self.send_btn is not None:
            self.send_btn.set_sensitive(False)
        if self.input is not None:
            # Allow composing/copying offline; send still blocked
            self.input.set_sensitive(True)
        return False

    def _apply_health(self, state: HealthState) -> None:
        """Update banner + soft flags. Never clears transcript or chats."""
        self._health = state
        if self._health_banner is None:
            return
        show = state.kind not in (HealthKind.OK,)
        # Hide "checking" banner once we have a real outcome? Show lightly for checking.
        if state.kind == HealthKind.CHECKING:
            show = True
        self._health_banner.set_visible(show)
        if not show:
            return
        if self._health_title is not None:
            self._health_title.set_text(state.title)
        if self._health_detail is not None:
            self._health_detail.set_text(state.detail)
        # Style
        for cls in ("error", "warn"):
            try:
                # health_inner is child of clamp
                child = self._health_banner.get_child()
                if child is not None:
                    child.remove_css_class(cls)
            except Exception:  # noqa: BLE001
                pass
        child = self._health_banner.get_child() if self._health_banner else None
        if child is not None:
            if state.kind in (
                HealthKind.OOM,
                HealthKind.STREAM_LOST,
                HealthKind.API_ERROR,
                HealthKind.MODEL_LOAD_FAILED,
            ):
                child.add_css_class("error")
            elif state.kind in (
                HealthKind.NOT_RUNNING,
                HealthKind.NOT_INSTALLED,
                HealthKind.NO_MODELS,
            ):
                child.add_css_class("warn")
        if self._health_action_btn is not None:
            if state.action_label and state.action:
                self._health_action_btn.set_visible(True)
                self._health_action_btn.set_label(state.action_label)
                self._health_action_id = state.action
                self._health_action_model = state.model
            else:
                self._health_action_btn.set_visible(False)
                self._health_action_id = None
                self._health_action_model = None

    def _on_health_action(self, *_args) -> None:
        action = self._health_action_id
        if action == "refresh":
            self._refresh_models()
        elif action == "retry_load":
            model = self._health_action_model or self._model
            if model:
                self._begin_model_load(model, greet=not self._messages)
            else:
                self._refresh_models()
        elif action == "dismiss":
            self._apply_health(
                HealthState(
                    kind=HealthKind.OK,
                    title="Ollama is ready",
                    detail="",
                )
            )
            self._health_banner.set_visible(False) if self._health_banner else None

    def _preferred_model(self) -> str | None:
        if self._conversation_id:
            try:
                conv = self._store.get_conversation(self._conversation_id)
                if conv is not None and conv.model:
                    return conv.model
            except Exception:  # noqa: BLE001
                pass
        return _load_last_model()

    def _set_load_controls_sensitive(self, enabled: bool) -> None:
        """Composer/model chrome: disabled only while a load is in flight."""
        if self.input is not None:
            self.input.set_sensitive(enabled and not self._streaming)
        if self.send_btn is not None:
            self.send_btn.set_sensitive(
                enabled and bool(self._model) and not self._streaming and not self._load_failed
            )
        if self.model_combo is not None:
            self.model_combo.set_sensitive(enabled)
        if self._refresh_btn is not None:
            self._refresh_btn.set_sensitive(enabled)
        if getattr(self, "_refresh_action", None) is not None:
            self._refresh_action.set_enabled(enabled)
        if self._clear_btn is not None:
            self._clear_btn.set_sensitive(enabled and not self._loading_model)
        nav = enabled and not self._streaming
        if self._new_chat_btn is not None:
            self._new_chat_btn.set_sensitive(nav)
        if self._sidebar_new_btn is not None:
            self._sidebar_new_btn.set_sensitive(nav)
        if self._sidebar_btn is not None:
            self._sidebar_btn.set_sensitive(enabled)
        if self._history_list is not None:
            self._history_list.set_sensitive(nav)

    # ---- model warm-up overlay ----

    def _show_load_overlay(
        self,
        *,
        model: str | None,
        title: str,
        status: str,
        pulse: bool = True,
        fraction: float | None = None,
    ) -> None:
        if self._load_overlay is None:
            return
        if self._load_title is not None:
            self._load_title.set_text(title)
        if self._load_model_label is not None:
            self._load_model_label.set_text(model or "")
            self._load_model_label.set_visible(bool(model))
        if self._load_status is not None:
            self._load_status.set_text(status)
        if self._load_progress is not None:
            if pulse or fraction is None:
                self._load_indeterminate = True
                self._load_progress.pulse()
                self._start_load_pulse()
            else:
                self._load_indeterminate = False
                self._stop_load_pulse()
                self._load_progress.set_fraction(max(0.0, min(1.0, fraction)))
        if self._load_spinner is not None:
            try:
                self._load_spinner.start()
            except Exception:  # noqa: BLE001
                pass
        self._load_overlay.set_visible(True)
        self._set_load_controls_sensitive(False)

    def _start_load_pulse(self) -> None:
        if self._load_pulse_id:
            return

        def tick() -> bool:
            if self._load_overlay is None or not self._load_overlay.get_visible():
                self._load_pulse_id = 0
                return False
            if self._load_indeterminate and self._load_progress is not None:
                self._load_progress.pulse()
            return True

        self._load_pulse_id = GLib.timeout_add(100, tick)

    def _stop_load_pulse(self) -> None:
        if self._load_pulse_id:
            try:
                GLib.source_remove(self._load_pulse_id)
            except Exception:  # noqa: BLE001
                pass
            self._load_pulse_id = 0

    def _hide_load_overlay(self) -> None:
        self._stop_load_pulse()
        if self._load_overlay is not None:
            self._load_overlay.set_visible(False)
        if self._load_spinner is not None:
            try:
                self._load_spinner.stop()
            except Exception:  # noqa: BLE001
                pass
        self._set_load_controls_sensitive(True)

    def _update_load_progress(self, chunk: dict) -> None:
        """Map Ollama NDJSON (status / completed / total) onto the overlay."""
        status = chunk.get("status")
        completed = chunk.get("completed")
        total = chunk.get("total")
        detail = None
        fraction = None
        if isinstance(completed, (int, float)) and isinstance(total, (int, float)) and total > 0:
            fraction = float(completed) / float(total)
            # Human-ish size line when we have bytes
            detail = f"{_fmt_bytes(completed)} / {_fmt_bytes(total)}"
        if isinstance(status, str) and status:
            line = status.replace("_", " ").capitalize()
            if detail:
                line = f"{line} · {detail}"
        elif detail:
            line = detail
        else:
            line = None

        if self._load_status is not None and line:
            self._load_status.set_text(line)
        if self._load_progress is not None:
            if fraction is not None:
                self._load_indeterminate = False
                self._stop_load_pulse()
                self._load_progress.set_fraction(max(0.0, min(1.0, fraction)))
            else:
                self._load_indeterminate = True
                self._load_progress.pulse()
                self._start_load_pulse()

    def _begin_model_load(self, model: str, *, greet: bool) -> None:
        if not model:
            return
        if self._streaming:
            return
        # Cancel any in-flight warm-up (model switch / retry)
        if self._loading_model:
            self._stop_load = True
        self._load_generation += 1
        gen = self._load_generation
        self._loading_model = True
        self._load_failed = False
        self._stop_load = False
        self._show_load_overlay(
            model=model,
            title="Loading model",
            status="Checking if the model is already in memory…",
            pulse=True,
        )
        self._set_status(f"Loading {model}…")

        def work() -> None:
            err: str | None = None
            try:
                already = self.client.is_model_loaded(model)
                if gen != self._load_generation:
                    return
                if already:
                    GLib.idle_add(
                        self._on_load_status,
                        gen,
                        model,
                        "Model already loaded",
                        "Ready.",
                        1.0,
                    )
                else:
                    GLib.idle_add(
                        self._on_load_status,
                        gen,
                        model,
                        "Loading model",
                        "Warming weights into memory…",
                        None,
                    )
                    for chunk in self.client.load_model(
                        model,
                        should_stop=lambda: self._stop_load
                        or gen != self._load_generation,
                    ):
                        if gen != self._load_generation:
                            return
                        GLib.idle_add(self._on_load_chunk, gen, chunk)
            except OllamaError as exc:
                err = str(exc)
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
            GLib.idle_add(self._on_model_load_finished, gen, model, err, greet)

        threading.Thread(target=work, daemon=True).start()

    def _on_load_status(
        self,
        gen: int,
        model: str,
        title: str,
        status: str,
        fraction: float | None,
    ) -> bool:
        if gen != self._load_generation:
            return False
        if self._load_title is not None:
            self._load_title.set_text(title)
        if self._load_model_label is not None:
            self._load_model_label.set_text(model)
            self._load_model_label.set_visible(True)
        if self._load_status is not None:
            self._load_status.set_text(status)
        if self._load_progress is not None:
            if fraction is None:
                self._load_indeterminate = True
                self._load_progress.pulse()
                self._start_load_pulse()
            else:
                self._load_indeterminate = False
                self._stop_load_pulse()
                self._load_progress.set_fraction(fraction)
        return False

    def _on_load_chunk(self, gen: int, chunk: dict) -> bool:
        if gen != self._load_generation:
            return False
        self._update_load_progress(chunk)
        return False

    def _on_model_load_finished(
        self, gen: int, model: str, err: str | None, greet: bool
    ) -> bool:
        if gen != self._load_generation:
            return False
        self._loading_model = False
        self._stop_load_pulse()
        if err:
            self._load_failed = True
            self._model = model
            self._hide_load_overlay()
            health = classify_error(err, context="load", model=model)
            self._apply_health(health)
            self._set_status("Load failed")
            # Transcript preserved; allow recovery without locking the window
            if self.model_combo is not None:
                self.model_combo.set_sensitive(True)
            if self._refresh_btn is not None:
                self._refresh_btn.set_sensitive(True)
            if self.input is not None:
                self.input.set_sensitive(True)
            if self.send_btn is not None:
                self.send_btn.set_sensitive(False)
            if self._clear_btn is not None:
                self._clear_btn.set_sensitive(True)
            if self._new_chat_btn is not None:
                self._new_chat_btn.set_sensitive(True)
            if self._sidebar_new_btn is not None:
                self._sidebar_new_btn.set_sensitive(True)
            if self._sidebar_btn is not None:
                self._sidebar_btn.set_sensitive(True)
            if self._history_list is not None:
                self._history_list.set_sensitive(True)
            return False

        self._load_failed = False
        if self._load_progress is not None:
            self._load_progress.set_fraction(1.0)
        if self._load_status is not None:
            self._load_status.set_text("Ready")
        self._hide_load_overlay()
        self._apply_health(
            HealthState(
                kind=HealthKind.OK,
                title="Ollama is ready",
                detail="Connected to the local Ollama service.",
            )
        )
        if self._health_banner is not None:
            self._health_banner.set_visible(False)
        self._set_status(model)
        _save_last_model(model)
        try:
            cid = self._ensure_conversation()
            self._store.set_model(cid, model)
        except Exception as exc:  # noqa: BLE001
            print(f"persist model failed: {exc}", flush=True)
        if greet and model not in self._greeted_models and not self._messages:
            self._greeted_models.add(model)
            self._show_ephemeral_greeting()
        if self.send_btn is not None:
            self.send_btn.set_sensitive(True)
        if self.input is not None:
            try:
                self.input.grab_focus()
            except Exception:  # noqa: BLE001
                pass
        return False

    def _show_ephemeral_greeting(self) -> None:
        """Empty-state opener only — not persisted, not sent to Ollama."""
        if self._messages:
            return
        if self._transcript_mode == "webkit" and self._web is not None:
            self._web.post(
                {
                    "type": "empty_state",
                    "title": GREETING_TEXT,
                    "subtitle": GREETING_SUB,
                }
            )
        else:
            # Native: ensure empty chrome exists, then set copy
            if self._empty_box is None or (
                self.chat_box is not None
                and self._empty_box.get_parent() is None
            ):
                if self.chat_box is not None:
                    while child := self.chat_box.get_first_child():
                        self.chat_box.remove(child)
                self._show_empty_state()
            if getattr(self, "_empty_title", None) is not None:
                self._empty_title.set_text(GREETING_TEXT)
            if getattr(self, "_empty_sub", None) is not None:
                self._empty_sub.set_text(GREETING_SUB)
        if self.send_btn is not None:
            self.send_btn.set_sensitive(True)

    def _request_stop(self) -> None:
        """Manual Stop: cancel the current stream, keep its partial output."""
        if self._active_stream_cancel is not None:
            self._active_stream_cancel.set()

    def _invalidate_active_stream(self) -> None:
        """Cancel the in-flight generation and mark it stale.

        Used when the active conversation changes out from under a running
        stream (switch / new chat / delete). Unlike manual Stop, this bumps
        the stream generation so the worker's pending UI and persistence
        callbacks see themselves as superseded and discard their output,
        even if the worker hasn't noticed the cancellation yet.
        """
        if self._active_stream_cancel is not None:
            self._active_stream_cancel.set()
        self._stream_generation += 1
        if self._streaming:
            try:
                self._stream_finished()
            except Exception:  # noqa: BLE001
                pass

    def _post_status_message(self, text: str, *, streaming: bool = False) -> str:
        """Show a non-persisted assistant-style note in the transcript (not LLM context)."""
        mid = self._next_msg_id("asst")
        if self._transcript_mode == "webkit" and self._web is not None:
            self._web.post(
                {
                    "type": "message_added",
                    "id": mid,
                    "role": "assistant",
                    "text": text,
                    "streaming": streaming,
                }
            )
        else:
            self._append_message(
                "assistant", text, message_id=mid, markdown=True
            )
        return mid

    def _try_composer_command(self, text: str) -> bool:
        """Handle ollama commands typed in the composer (HTTP API — not LLM)."""
        raw = (text or "").strip()
        if not raw.lower().startswith("ollama"):
            return False

        pull = _RE_OLLAMA_PULL.match(raw)
        if pull:
            self._run_ollama_pull(pull.group(1))
            return True
        if _RE_OLLAMA_LIST.match(raw):
            self._run_ollama_info("list")
            return True
        if _RE_OLLAMA_PS.match(raw):
            self._run_ollama_info("ps")
            return True

        self._post_status_message(
            "Composer command not recognized.\n\n"
            "Supported:\n"
            "- `ollama pull <model-name>`\n"
            "- `ollama list`\n"
            "- `ollama ps`\n\n"
            "Example: `ollama pull llama3.2`"
        )
        return True

    def _composer_cmd_busy(self) -> bool:
        return bool(getattr(self, "_ollama_cli_busy", False))

    def _set_composer_cmd_busy(self, busy: bool) -> None:
        self._ollama_cli_busy = busy
        if self.send_btn is not None and not busy:
            self.send_btn.set_sensitive(
                bool(self._model)
                and not self._streaming
                and not self._loading_model
                and not self._load_failed
            )
        elif self.send_btn is not None and busy:
            self.send_btn.set_sensitive(False)

    def _update_status_message(self, mid: str, text: str, *, done: bool = False) -> None:
        """Push progressive status text into a non-chat transcript bubble."""
        if self._transcript_mode == "webkit" and self._web is not None:
            if done:
                self._web.post({"type": "message_done", "id": mid, "text": text})
            else:
                # Full replace of displayed text (not a delta chunk)
                self._web.post(
                    {
                        "type": "message_reset",
                        "id": mid,
                        "text": text,
                        "streaming": True,
                    }
                )
        else:
            try:
                self._native_remove_message(mid)
            except Exception:  # noqa: BLE001
                pass
            self._append_message("assistant", text, message_id=mid, markdown=True)

    @staticmethod
    def _format_pull_progress(chunk: dict) -> str:
        """Human line from a /api/pull NDJSON object (no ANSI)."""
        status = chunk.get("status")
        status_s = str(status).replace("_", " ") if status else "Working"
        completed = chunk.get("completed")
        total = chunk.get("total")
        digest = chunk.get("digest") or chunk.get("layer")
        parts = [status_s]
        if isinstance(completed, (int, float)) and isinstance(total, (int, float)) and total > 0:
            pct = 100.0 * float(completed) / float(total)
            parts.append(
                f"{_fmt_bytes(completed)} / {_fmt_bytes(total)} ({pct:.0f}%)"
            )
        elif isinstance(digest, str) and digest:
            short = digest if len(digest) <= 20 else digest[:12] + "…"
            parts.append(short)
        return " · ".join(parts)

    def _run_ollama_pull(self, model: str) -> None:
        """Pull via POST /api/pull stream — clean JSON progress, no CLI ANSI."""
        if self._composer_cmd_busy():
            self._post_status_message(
                "An Ollama command is already running. Wait for it to finish."
            )
            return
        label = f"ollama pull {model}"
        self._set_composer_cmd_busy(True)
        mid = self._post_status_message(f"**Pulling** `{model}`…\n\n_starting_", streaming=True)
        self._set_status(f"Pulling {model}…")

        def work() -> None:
            lines: list[str] = []
            last_ui = ""
            ok = False
            err_msg: str | None = None
            try:
                for chunk in self.client.pull_model(model):
                    line = self._format_pull_progress(chunk)
                    status = (chunk.get("status") or "").lower()
                    # Keep a short rolling log of distinct status lines
                    if line and (not lines or lines[-1] != line):
                        # Replace last download line when only % changes on same phase
                        if (
                            lines
                            and " / " in lines[-1]
                            and " / " in line
                            and lines[-1].split(" · ")[0] == line.split(" · ")[0]
                        ):
                            lines[-1] = line
                        else:
                            lines.append(line)
                            # Cap history so the bubble stays readable
                            if len(lines) > 12:
                                lines = lines[-12:]
                    body = f"**Pulling** `{model}`…\n\n" + "\n".join(f"- {x}" for x in lines)
                    if body != last_ui:
                        last_ui = body
                        GLib.idle_add(
                            lambda b=body: (
                                self._update_status_message(mid, b, done=False) or False
                            )
                        )
                    if status == "success":
                        ok = True
                if not ok and not err_msg:
                    # Stream ended without explicit success — treat as ok if no error raised
                    ok = True
            except OllamaError as exc:
                err_msg = str(exc)
                ok = False
            except Exception as exc:  # noqa: BLE001
                err_msg = str(exc)
                ok = False

            if ok:
                final = (
                    f"**Pull complete:** `{model}`\n\n"
                    + ("\n".join(f"- {x}" for x in lines) if lines else "_Done._")
                    + "\n\n_Refreshing model list…_"
                )
            else:
                final = (
                    f"**Pull failed:** `{model}`\n\n"
                    + (f"{err_msg}\n\n" if err_msg else "")
                    + ("\n".join(f"- {x}" for x in lines) if lines else "")
                )

            def done() -> bool:
                self._update_status_message(mid, final, done=True)
                self._set_composer_cmd_busy(False)
                if ok:
                    self._refresh_models()
                else:
                    self._set_status(self._model or "Ready")
                return False

            GLib.idle_add(done)

        threading.Thread(target=work, daemon=True).start()

    def _run_ollama_info(self, kind: str) -> None:
        """ollama list / ps via HTTP (/api/tags, /api/ps) — structured text."""
        if self._composer_cmd_busy():
            self._post_status_message(
                "An Ollama command is already running. Wait for it to finish."
            )
            return
        label = f"ollama {kind}"
        self._set_composer_cmd_busy(True)
        mid = self._post_status_message(f"Running `{label}`…", streaming=True)
        self._set_status(f"Running {label}…")

        def work() -> None:
            try:
                if kind == "list":
                    body = f"**Installed models** (`ollama list`)\n\n{self.client.format_list_models()}"
                else:
                    body = f"**Loaded models** (`ollama ps`)\n\n{self.client.format_ps_models()}"
                ok = True
            except OllamaError as exc:
                body = f"**`{label}` failed:** {exc}"
                ok = False
            except Exception as exc:  # noqa: BLE001
                body = f"**`{label}` failed:** {exc}"
                ok = False

            def done() -> bool:
                self._update_status_message(mid, body, done=True)
                self._set_composer_cmd_busy(False)
                self._set_status(self._model or "Ready")
                return False

            GLib.idle_add(done)

        threading.Thread(target=work, daemon=True).start()

    def _send(self) -> None:
        if self._streaming or self._loading_model:
            return
        if getattr(self, "_ollama_cli_busy", False):
            return
        buf = self.input.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
        if not text:
            return

        # Local ollama CLI commands (e.g. ollama pull llama3.2) — never chat to the model
        if self._try_composer_command(text):
            buf.set_text("", -1)
            return

        if getattr(self, "_health", None) is not None and not self._health.can_chat:
            # Re-probe — user may have fixed Ollama since the banner appeared
            self._refresh_models()
            return
        if not self._model:
            return
        buf.set_text("", -1)
        uid = self._next_msg_id("user")
        if self._transcript_mode == "webkit" and self._web is not None:
            self._web.post(
                {
                    "type": "message_added",
                    "id": uid,
                    "role": "user",
                    "text": text,
                    "streaming": False,
                }
            )
        else:
            self._append_message("user", text, message_id=uid)
        self._messages.append({"id": uid, "role": "user", "content": text})
        self._persist_message("user", text, message_id=uid)
        self._sync_composer_hint()
        self._start_assistant_stream(mode="new")

    def _remove_empty_state(self) -> None:
        if self.chat_box is not None:
            if self._empty_box is not None and self._empty_box.get_parent() is not None:
                self.chat_box.remove(self._empty_box)
                self._empty_box = None
                self.chat_box.set_valign(Gtk.Align.START)
                self.chat_box.set_vexpand(False)
        self._sync_composer_hint()

    def _append_message(
        self,
        role: str,
        content: str,
        *,
        typing: bool = False,
        markdown: bool = False,
        message_id: str | None = None,
    ) -> MessageBody:
        self._remove_empty_state()
        is_user = role == "user"
        mid = message_id or self._next_msg_id("user" if is_user else "asst")
        now = datetime.now().strftime("%I:%M %p").lstrip("0")

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("msg-row")
        row.add_css_class("msg-row-user" if is_user else "msg-row-assistant")
        row.set_name(mid)
        if is_user:
            row.set_halign(Gtk.Align.END)
        else:
            row.set_halign(Gtk.Align.FILL)
        row.set_hexpand(True)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        col.set_hexpand(True)
        if is_user:
            col.set_halign(Gtk.Align.END)
            col.set_hexpand(False)
        else:
            col.set_halign(Gtk.Align.FILL)
            col.set_hexpand(True)

        bubble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        bubble.add_css_class("chat-bubble")
        bubble.add_css_class("chat-user" if is_user else "chat-assistant")
        if is_user:
            bubble.set_halign(Gtk.Align.END)
            bubble.set_hexpand(False)
        else:
            bubble.set_halign(Gtk.Align.FILL)
            bubble.set_hexpand(True)

        body = MessageBody(role=role)
        body._message_id = mid  # type: ignore[attr-defined]
        if not is_user:
            body.set_hexpand(True)
            body.set_halign(Gtk.Align.FILL)
        if typing:
            body.set_typing()
        elif markdown and not is_user:
            body.set_markdown(content)
        elif is_user:
            body.set_plain(content)
        else:
            body.set_markdown(content)

        bubble.append(body)

        meta = Gtk.Label(label=now)
        meta.add_css_class("chat-meta")
        if is_user:
            meta.add_css_class("chat-user-meta")
        meta.set_halign(Gtk.Align.END if is_user else Gtk.Align.START)

        col.append(bubble)
        # Actions under bubble (user: Copy/Edit/Regenerate; assistant: full set)
        if not typing:
            col.append(
                self._native_action_bar(
                    mid, body, content, role=role, is_user=is_user
                )
            )
        col.append(meta)
        row.append(col)

        self.chat_box.append(row)
        self._native_rows[mid] = row
        self._scroll_to_end()
        return body

    def _native_action_bar(
        self,
        message_id: str,
        body: MessageBody,
        raw_markdown: str,
        *,
        role: str = "assistant",
        is_user: bool = False,
    ) -> Gtk.Widget:
        """Icon strip: Copy · Regenerate · Continue · Delete · More (assistant)."""
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        bar.set_halign(Gtk.Align.END if is_user else Gtk.Align.START)

        def icon_btn(
            icon_name: str, tooltip: str, handler, *, destructive: bool = False
        ) -> Gtk.Button:
            btn = Gtk.Button.new_from_icon_name(icon_name)
            btn.add_css_class("flat")
            btn.add_css_class("circular")
            if destructive:
                btn.add_css_class("destructive-action")
            btn.set_has_frame(False)
            btn.set_tooltip_text(tooltip)
            btn.set_size_request(32, 32)
            btn.connect("clicked", handler)
            bar.append(btn)
            return btn

        def current_text() -> str:
            idx = self._find_message_index(message_id)
            if idx >= 0:
                return self._messages[idx].get("content") or raw_markdown
            return raw_markdown

        copy_tip = "Copy message" if is_user else "Copy response"
        icon_btn(
            "edit-copy-symbolic",
            copy_tip,
            lambda *_: self._clipboard_set(current_text()),
        )
        if is_user:
            # Copy · Edit · Regenerate · Delete
            icon_btn(
                "document-edit-symbolic",
                "Edit message",
                lambda *_: self._native_edit_user(message_id, current_text()),
            )
            icon_btn(
                "media-playlist-repeat-symbolic",
                "Regenerate response",
                lambda *_: self._regenerate_message(message_id),
            )
            icon_btn(
                "user-trash-symbolic",
                "Delete message",
                lambda *_: self._delete_message(message_id),
                destructive=True,
            )
            return bar

        # Copy · Regenerate · Continue · Delete · More
        icon_btn(
            "media-playlist-repeat-symbolic",
            "Regenerate response",
            lambda *_: self._regenerate_message(message_id),
        )
        icon_btn(
            "media-playback-start-symbolic",
            "Continue generating",
            lambda *_: self._continue_message(message_id),
        )
        icon_btn(
            "user-trash-symbolic",
            "Delete message",
            lambda *_: self._delete_message(message_id),
            destructive=True,
        )

        more = Gtk.MenuButton()
        more.set_icon_name("view-more-symbolic")
        more.add_css_class("flat")
        more.set_has_frame(False)
        more.set_tooltip_text("More actions")
        more.set_size_request(32, 32)
        pop = Gtk.Popover()
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        col.set_margin_top(6)
        col.set_margin_bottom(6)
        col.set_margin_start(6)
        col.set_margin_end(6)

        md_btn = Gtk.Button(label="Copy as Markdown")
        md_btn.add_css_class("flat")
        md_btn.connect(
            "clicked",
            lambda *_: (
                pop.popdown(),
                self._clipboard_set(current_text()),
            ),
        )
        col.append(md_btn)
        pop.set_child(col)
        more.set_popover(pop)
        bar.append(more)
        return bar

    def _native_edit_user(self, message_id: str, initial: str) -> None:
        """Simple modal edit for native transcript."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Edit message",
            body="Change your prompt and resubmit. Later replies will be replaced.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save & submit")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        entry = Gtk.TextView()
        entry.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        entry.set_size_request(320, 120)
        buf = entry.get_buffer()
        buf.set_text(initial or "")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(100)
        scroller.set_child(entry)
        scroller.set_margin_top(8)
        # Adw.MessageDialog extra child
        try:
            dialog.set_extra_child(scroller)
        except Exception:  # noqa: BLE001
            # Older libadwaita fallback: use body only
            pass

        def on_response(dlg, response: str) -> None:
            if response != "save":
                return
            start, end = buf.get_bounds()
            text = buf.get_text(start, end, False).strip()
            if text:
                self._edit_resend_message(message_id, text)

        dialog.connect("response", on_response)
        dialog.present()

    def _native_remove_message(self, message_id: str) -> None:
        row = self._native_rows.pop(message_id, None)
        if row is not None and self.chat_box is not None:
            try:
                self.chat_box.remove(row)
            except Exception:  # noqa: BLE001
                pass

    def _scroll_to_end(self) -> None:
        if self.scroller is None:
            return
        adj = self.scroller.get_vadjustment()

        def _do():
            adj.set_value(adj.get_upper() - adj.get_page_size())
            return False

        GLib.idle_add(_do)

    def _start_assistant_stream(
        self,
        *,
        mode: str = "new",
        assistant_id: str | None = None,
        seed_text: str = "",
        api_messages: list[dict[str, str]] | None = None,
    ) -> None:
        """mode: new | replace | continue."""
        if self._streaming:
            return
        self._stream_generation += 1
        my_generation = self._stream_generation
        cancel_event = threading.Event()
        self._active_stream_cancel = cancel_event
        origin_conversation_id = self._conversation_id
        origin_model = self._model or ""
        self._streaming = True
        self.send_btn.set_sensitive(False)
        self.send_btn.set_visible(False)
        self.stop_btn.set_visible(True)
        self.stop_btn.set_sensitive(True)
        self._set_status("Thinking…")

        use_web = self._transcript_mode == "webkit" and self._web is not None
        body: MessageBody | None = None
        stream_serial = 0
        if mode in ("replace", "continue") and assistant_id:
            aid = assistant_id
        else:
            aid = self._next_msg_id("asst")
        # Continue: transcript seed ends with a blank-line boundary so new tokens
        # never fuse to the previous last character (e.g. "🌐Here's").
        stream_seed = (
            continue_seed_for_stream(seed_text) if mode == "continue" else seed_text
        )

        if use_web:
            if mode == "replace":
                self._web.post(
                    {
                        "type": "message_reset",
                        "id": aid,
                        "streaming": True,
                        "text": "",
                    }
                )
            elif mode == "continue":
                # Seed already ends with blank-line boundary so deltas don't fuse
                self._web.post(
                    {
                        "type": "message_reset",
                        "id": aid,
                        "streaming": True,
                        "text": stream_seed,
                    }
                )
            else:
                self._web.post(
                    {
                        "type": "message_added",
                        "id": aid,
                        "role": "assistant",
                        "text": "",
                        "streaming": True,
                    }
                )
        else:
            if mode == "replace":
                self._native_remove_message(aid)
                body = self._append_message(
                    "assistant", "···", typing=True, message_id=aid
                )
            elif mode == "continue":
                # Rebuild row as streaming from seed + boundary
                self._native_remove_message(aid)
                body = self._append_message(
                    "assistant", stream_seed or "···", typing=True, message_id=aid
                )
                if stream_seed:
                    body.append_stream(stream_seed)
            else:
                body = self._append_message(
                    "assistant", "···", typing=True, message_id=aid
                )
            body._render_serial = getattr(body, "_render_serial", 0) + 1
            stream_serial = body._render_serial

        pending: list[str] = []
        collected: list[str] = []
        state = {
            "streaming": True,
            "error": None,
            "ui_done": False,
            "lock": threading.Lock(),
        }
        outbound = (
            api_messages
            if api_messages is not None
            else self._api_messages()
        )

        def still_current() -> bool:
            if my_generation != self._stream_generation:
                return False
            if use_web:
                return True
            assert body is not None
            return getattr(body, "_render_serial", 0) == stream_serial

        def finalize_ui() -> None:
            if state["ui_done"] or not still_current():
                return
            state["ui_done"] = True
            err = state["error"]
            piece = "".join(collected)
            if mode == "continue":
                final = join_continue(seed_text, piece)
            else:
                final = piece

            if err is not None:
                # Keep partial transcript; surface plain-language recovery
                self._apply_health(
                    classify_error(
                        err,
                        context="stream",
                        model=origin_model,
                    )
                )

            if use_web and self._web is not None:
                if err is not None:
                    self._web.post(
                        {
                            "type": "message_error",
                            "id": aid,
                            "text": (
                                f"Error: {err}"
                                if not final
                                else final + f"\n\n[Error: {err}]"
                            ),
                        }
                    )
                else:
                    self._web.post(
                        {
                            "type": "message_done",
                            "id": aid,
                            "text": final or "(no response)",
                        }
                    )
                self._commit_assistant_result(
                    aid,
                    final,
                    mode=mode,
                    origin_conversation_id=origin_conversation_id,
                    allow_empty=bool(err),
                )
                self._stream_finished()
                return

            assert body is not None
            if err is not None:
                parent = body.get_parent()
                if parent is not None:
                    parent.add_css_class("chat-error")
                body.set_plain(
                    f"Error: {err}" if not final else final + f"\n\n[Error: {err}]"
                )
            elif final:
                body.finish_stream()
            else:
                body.set_plain("(no response)")
            self._commit_assistant_result(
                aid,
                final,
                mode=mode,
                origin_conversation_id=origin_conversation_id,
                allow_empty=bool(err),
            )
            # Refresh native action bar with final text
            if mode in ("replace", "continue", "new") and final:
                self._native_remove_message(aid)
                self._append_message(
                    "assistant", final, markdown=True, message_id=aid
                )
            self._scroll_to_end()
            self._stream_finished()

        def flush_stream() -> bool:
            """~30 fps paced append — single renderer only (native XOR webkit)."""
            if not still_current():
                return False
            with state["lock"]:
                chunk = "".join(pending) if pending else ""
                pending.clear()
                still_streaming = state["streaming"]

            if chunk:
                if use_web and self._web is not None:
                    self._web.post(
                        {
                            "type": "message_delta",
                            "id": aid,
                            "text": chunk,
                        }
                    )
                elif body is not None:
                    body.append_stream(chunk)
                    self._scroll_to_end()

            if still_streaming:
                return True

            with state["lock"]:
                leftover = "".join(pending) if pending else ""
                pending.clear()
            if leftover and still_current():
                if use_web and self._web is not None:
                    self._web.post(
                        {
                            "type": "message_delta",
                            "id": aid,
                            "text": leftover,
                        }
                    )
                elif body is not None:
                    body.append_stream(leftover)
                    self._scroll_to_end()
            finalize_ui()
            return False

        GLib.timeout_add(33, flush_stream)

        def work():
            try:
                for piece in self.client.chat_stream(
                    origin_model,
                    list(outbound),
                    cancel_event=cancel_event,
                ):
                    collected.append(piece)
                    with state["lock"]:
                        pending.append(piece)
            except OllamaError as exc:
                with state["lock"]:
                    state["error"] = str(exc)
            finally:
                with state["lock"]:
                    state["streaming"] = False

        threading.Thread(target=work, daemon=True).start()

    def _commit_assistant_result(
        self,
        assistant_id: str,
        final: str,
        *,
        mode: str,
        origin_conversation_id: str,
        allow_empty: bool = False,
    ) -> None:
        if not final and not allow_empty:
            return
        text = final or "(no response)"
        idx = self._find_message_index(assistant_id)
        if mode == "continue" and idx >= 0:
            self._messages[idx]["content"] = text
            try:
                self._store.update_message(assistant_id, text)
            except Exception as exc:  # noqa: BLE001
                print(f"continue persist: {exc}", flush=True)
            return
        if mode == "replace":
            if idx >= 0:
                self._messages[idx]["content"] = text
            else:
                self._messages.append(
                    {"id": assistant_id, "role": "assistant", "content": text}
                )
            try:
                # Row was deleted before stream; re-insert into the
                # conversation the stream actually belongs to.
                self._store.append_message(
                    origin_conversation_id,
                    role="assistant",
                    content=text,
                    message_id=assistant_id,
                )
            except Exception as exc:  # noqa: BLE001
                # Might already exist if delete failed — try update
                try:
                    self._store.update_message(assistant_id, text)
                except Exception as exc2:  # noqa: BLE001
                    print(f"replace persist: {exc} / {exc2}", flush=True)
            return
        # new
        self._messages.append(
            {"id": assistant_id, "role": "assistant", "content": text}
        )
        try:
            self._store.append_message(
                origin_conversation_id,
                role="assistant",
                content=text,
                message_id=assistant_id,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"persist message failed: {exc}", flush=True)

    def _stream_finished(self) -> bool:
        self._streaming = False
        self._active_stream_cancel = None
        self.send_btn.set_sensitive(bool(self._model))
        self.send_btn.set_visible(True)
        self.stop_btn.set_visible(False)
        self.stop_btn.set_sensitive(False)
        if self._model:
            self._set_status(self._model)
        else:
            self._set_status("Ready")
        return False


def _fmt_bytes(n: float | int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"
