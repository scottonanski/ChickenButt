#!/usr/bin/env python3
"""Regression: sidebar interaction polish — pointer cursors on clickable
controls, the model selector living in the sidebar (not under the header),
and the sidebar always starting closed regardless of a stale settings file.

Real ChatSidebar + real WebKit view + real GLib loop, same pattern as the
other scripts/test_*.py files. Model refresh/load network calls are
monkeypatched on the real OllamaClient instance (fake models, instant
"already loaded") so the real production _refresh_models -> _on_model_selected
-> _begin_model_load -> _save_last_model chain runs end-to-end without
needing a real Ollama server.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib  # noqa: E402

from ollama_client import OllamaClient  # noqa: E402
from window import ChatSidebar  # noqa: E402


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


def pump(seconds: float = 0.0) -> None:
    ctx = GLib.main_context_default()
    deadline = time.time() + seconds
    while True:
        while ctx.pending():
            ctx.iteration(False)
        if time.time() >= deadline:
            break
        time.sleep(0.01)


def wait_until(cond, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        pump(0.02)
        if cond():
            return True
    return False


def cursor_name(widget) -> str | None:
    cur = widget.get_cursor()
    return cur.get_name() if cur is not None else None


def is_descendant(widget, ancestor) -> bool:
    p = widget.get_parent()
    while p is not None:
        if p is ancestor:
            return True
        p = p.get_parent()
    return False


def child_index(container, target) -> int:
    """Index of target among container's direct children, or -1."""
    i = 0
    child = container.get_first_child()
    while child is not None:
        if child is target:
            return i
        child = child.get_next_sibling()
        i += 1
    return -1


def direct_child_ancestor(widget, container):
    """Walk up from widget to find the ancestor that is a direct child of
    container — skips GTK-internal wrappers like the Gtk.Viewport a
    ScrolledWindow inserts around a non-Gtk.Scrollable child."""
    w = widget
    while w is not None:
        parent = w.get_parent()
        if parent is container:
            return w
        w = parent
    return None


def eval_js(web, js: str) -> None:
    web._view.evaluate_javascript(js, -1, None, None, None, None, None)


def eval_js_value(web, js: str, captured: dict, timeout: float = 10.0):
    def cb(_gobj, res, *_a):
        try:
            val = web._view.evaluate_javascript_finish(res)
            captured["json"] = val.to_json(0) if val is not None else None
        except Exception as exc:  # noqa: BLE001
            captured["error"] = repr(exc)

    captured.pop("json", None)
    captured.pop("error", None)
    web._view.evaluate_javascript(js, -1, None, None, None, cb, None)
    wait_until(lambda: "json" in captured or "error" in captured, timeout=timeout)
    if "json" in captured:
        raw = captured["json"]
        # evaluate_javascript_finish's to_json double-encodes string results.
        try:
            return json.loads(json.loads(raw))
        except (TypeError, json.JSONDecodeError):
            return json.loads(raw) if raw is not None else None
    return None


def main() -> int:
    results = Results()

    TMP = Path(tempfile.mkdtemp(prefix="cb-sidebar-interactions-"))
    os.environ["CHICKENBUTT_DB"] = str(TMP / "db.sqlite")
    os.environ["XDG_CONFIG_HOME"] = str(TMP / "config")
    os.environ["XDG_DATA_HOME"] = str(TMP / "data")

    # Seed a stale settings file with the old, no-longer-read sidebar_open
    # key set to true, BEFORE constructing any window — proves it's ignored
    # rather than merely untested.
    settings_dir = TMP / "config" / "chickenbutt"
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / "settings.json").write_text(
        json.dumps({"sidebar_open": True}), encoding="utf-8"
    )

    Adw.init()
    app = Adw.Application(
        application_id="dev.local.chickenbutt.sidebarinteractions",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    holder: dict = {"win": None}

    def on_activate(a):
        holder["win"] = ChatSidebar(a, client=OllamaClient())
        holder["win"].present()

    app.connect("activate", on_activate)
    app.register()
    app.activate()
    win: ChatSidebar = holder["win"]
    assert win is not None
    pump(0.5)

    # === [1] Startup: sidebar hidden, toggle inactive ===
    print("\n[1] Startup sidebar state (despite a stale sidebar_open=true settings file)", flush=True)
    results.check("sidebar hidden on startup", win._sidebar.get_visible() is False)
    results.check(
        "stale sidebar_open=true in settings.json was ignored",
        win._sidebar.get_visible() is False,
    )
    results.check("sidebar toggle button inactive on startup", win._sidebar_btn.get_active() is False)

    # === [2] Opening/closing still works ===
    print("\n[2] Opening and closing the sidebar", flush=True)
    win.toggle_sidebar(True)
    pump(0.1)
    results.check("toggle_sidebar(True) opens it", win._sidebar.get_visible() is True)
    results.check("toggle button reflects open state", win._sidebar_btn.get_active() is True)
    win.toggle_sidebar(False)
    pump(0.1)
    results.check("toggle_sidebar(False) closes it", win._sidebar.get_visible() is False)
    results.check("toggle button reflects closed state", win._sidebar_btn.get_active() is False)

    # === [3] Model dropdown lives in the sidebar's Model section ===
    print("\n[3] Model dropdown location", flush=True)
    results.check(
        "exactly one model dropdown, a descendant of the sidebar",
        win.model_combo is not None and is_descendant(win.model_combo, win._sidebar),
    )
    scroller = direct_child_ancestor(win._history_list, win._sidebar)
    model_box = direct_child_ancestor(win.model_combo, win._sidebar)
    foot = direct_child_ancestor(win._settings_btn, win._sidebar)
    idx_scroller = child_index(win._sidebar, scroller)
    idx_model = child_index(win._sidebar, model_box)
    idx_foot = child_index(win._sidebar, foot)
    results.check(
        "model section appears after the conversation list",
        -1 not in (idx_scroller, idx_model) and idx_model > idx_scroller,
        f"scroller={idx_scroller} model={idx_model}",
    )
    results.check(
        "model section appears before the Settings footer",
        -1 not in (idx_model, idx_foot) and idx_model < idx_foot,
        f"model={idx_model} foot={idx_foot}",
    )
    w, h = win.model_combo.get_size_request()
    results.check("model dropdown is no longer fixed to 320px wide", w != 320, f"size_request={(w, h)}")
    results.check("model dropdown keeps its 38px height", h == 38, f"size_request={(w, h)}")

    # === [4] Health banner stays in the main chat column ===
    print("\n[4] Health banner location", flush=True)
    chat_column = win._transcript_widget.get_parent()
    outer = chat_column.get_parent()
    results.check(
        "health banner is not a descendant of the sidebar",
        not is_descendant(win._health_banner, win._sidebar),
    )
    results.check(
        "health banner shares the main-content container with the transcript",
        win._health_banner.get_parent() is outer,
    )

    # === [5] Model selection and last-model persistence still work ===
    print("\n[5] Model selection and last-model persistence (real refresh/select/load chain)", flush=True)
    # Let the real cold-start model probe/warm-up (kicked off from __init__)
    # settle first, same gotcha noted in HANDOFF.md for other tests — otherwise
    # our explicit _refresh_models() call below just no-ops against the
    # in-flight real one (_loading_model guard) and we'd observe the real
    # model instead of the fake ones we're about to substitute.
    wait_until(lambda: not win._loading_model, timeout=60.0)
    pump(0.2)
    win.client.list_models = lambda: ["fake-model-a", "fake-model-b"]
    win.client.is_model_loaded = lambda model: True
    win._refresh_models()
    ok = wait_until(lambda: win._model == "fake-model-a" and not win._loading_model, timeout=15.0)
    pump(0.2)
    results.check("initial refresh selects and loads the first fake model", ok, str(win._model))
    from window import _load_last_model

    results.check(
        "last-model persisted after initial load",
        _load_last_model() == "fake-model-a",
        str(_load_last_model()),
    )
    win.model_combo.set_selected(1)
    ok = wait_until(lambda: win._model == "fake-model-b" and not win._loading_model, timeout=15.0)
    pump(0.2)
    results.check("selecting a different model in the dropdown still loads it", ok, str(win._model))
    results.check(
        "last-model persistence follows the new selection",
        _load_last_model() == "fake-model-b",
        str(_load_last_model()),
    )

    # === [6] Representative GTK click targets report the pointer cursor ===
    print("\n[6] GTK pointer cursor on representative click targets", flush=True)
    for label, widget in (
        ("sidebar toggle", win._sidebar_btn),
        ("clear conversation", win._clear_btn),
        ("refresh models", win._refresh_btn),
        ("model dropdown", win.model_combo),
        ("sidebar new chat", win._sidebar_new_btn),
        ("sidebar settings", win._settings_btn),
        ("health banner action", win._health_action_btn),
        ("send", win.send_btn),
        ("stop", win.stop_btn),
    ):
        results.check(f"{label} reports pointer cursor", cursor_name(widget) == "pointer", str(cursor_name(widget)))

    # === [7] A generated conversation row + its overflow button ===
    print("\n[7] Conversation row + overflow control pointer cursor", flush=True)
    conv = win._store.create_conversation(model="fake-model-a")
    win._store.append_message(conv.id, role="user", content="hi", message_id="m1")
    win._history_dirty = True
    win._rebuild_history_list()
    pump(0.1)
    row = win._history_list.get_first_child()
    found_row = None
    while row is not None:
        if row.get_name() == conv.id:
            found_row = row
            break
        row = row.get_next_sibling()
    results.check("generated conversation row found", found_row is not None)
    if found_row is not None:
        results.check("conversation row reports pointer cursor", cursor_name(found_row) == "pointer")
        outer_box = found_row.get_child()
        more_btn = outer_box.get_last_child() if outer_box is not None else None
        results.check(
            "row's overflow (more) button reports pointer cursor",
            more_btn is not None and cursor_name(more_btn) == "pointer",
        )

    # === [8] WebKit: links, code controls, message-action buttons vs. plain text ===
    if win._transcript_mode == "webkit" and win._web is not None:
        print("\n[8] WebKit computed cursor: pointer for interactive elements, not prose", flush=True)
        web = win._web
        wait_until(lambda: web._ready, timeout=20.0)
        pump(0.3)
        web._view.evaluate_javascript(
            "window.chickenbuttApply({"
            "type: 'conversation_reset',"
            "messages: [{id: 'cursor-check', role: 'assistant', "
            "content: 'Plain prose. [a link](https://example.com/safe)\\n\\n"
            "```python\\nprint(1)\\n```\\n'}]"
            "});",
            -1, None, None, None, None, None,
        )
        pump(0.5)
        captured: dict = {}
        report = eval_js_value(
            web,
            "(function(){"
            "  const root = document.querySelector('[data-id=\"cursor-check\"]');"
            "  function cur(sel) {"
            "    const el = root.querySelector(sel);"
            "    return el ? getComputedStyle(el).cursor : null;"
            "  }"
            "  return JSON.stringify({"
            "    link: cur('a'),"
            "    copyBtn: cur('[data-copy]'),"
            "    expandBtn: cur('[data-expand]'),"
            "    actionBtn: cur('.msg-actions [data-action]') || cur('.msg-actions button'),"
            "    prose: cur('p'),"
            "  });"
            "})();",
            captured,
        )
        results.check("link computed cursor is pointer", (report or {}).get("link") == "pointer", str(report))
        results.check("code copy control computed cursor is pointer", (report or {}).get("copyBtn") == "pointer", str(report))
        results.check("code expand control computed cursor is pointer", (report or {}).get("expandBtn") == "pointer", str(report))
        results.check(
            "message-action control computed cursor is pointer",
            (report or {}).get("actionBtn") == "pointer",
            str(report),
        )
        results.check(
            "noninteractive prose text does NOT compute to pointer",
            (report or {}).get("prose") not in ("pointer", None),
            str(report),
        )
    else:
        print("\n[8] Skipped (native transcript mode)", flush=True)

    # === [9] A genuinely new window construction also starts closed ===
    print("\n[9] A fresh ChatSidebar construction starts closed again", flush=True)
    # Re-assert the stale flag right before this specific construction, in
    # case anything upstream rewrote settings.json without it.
    settings_path = TMP / "config" / "chickenbutt" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.is_file() else {}
    data["sidebar_open"] = True
    settings_path.write_text(json.dumps(data), encoding="utf-8")

    app2 = Adw.Application(
        application_id="dev.local.chickenbutt.sidebarinteractions2",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    holder2: dict = {"win": None}

    def on_activate2(a):
        holder2["win"] = ChatSidebar(a, client=OllamaClient())
        holder2["win"].present()

    app2.connect("activate", on_activate2)
    app2.register()
    app2.activate()
    win2: ChatSidebar = holder2["win"]
    assert win2 is not None
    pump(0.3)
    results.check(
        "a freshly constructed second window also starts with the sidebar hidden",
        win2._sidebar.get_visible() is False,
    )
    results.check(
        "its sidebar toggle button is also inactive",
        win2._sidebar_btn.get_active() is False,
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
