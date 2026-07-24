#!/usr/bin/env python3
"""Regression: settings, composer geometry, and sidebar interaction behavior.

Covers the Phase-1 settings seam, the complete Phase-3 composer
characterization surface, pointer cursors on clickable controls, the model
selector living in the sidebar (not under the header), and the sidebar always
starting closed regardless of a stale settings file.

Real ChatSidebar + real WebKit view + real GLib loop, same pattern as the
other scripts/test_*.py files. Model refresh/load network calls are
monkeypatched on the real OllamaClient instance (fake models, instant
"already loaded") so the real production _refresh_models -> _on_model_selected
-> _begin_model_load -> _save_last_model chain runs end-to-end without
needing a real Ollama server.
"""
from __future__ import annotations

import contextlib
import io
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
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from composer_geometry import ComposerGeometry  # noqa: E402
from ollama_client import OllamaClient  # noqa: E402
import window as window_module  # noqa: E402
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


def characterize_settings(
    results: Results,
    settings_dir: Path,
    settings_path: Path,
) -> None:
    """Lock down the settings helpers before their Phase-2 extraction."""
    print("\n[0] Settings helper characterization", flush=True)

    window_module._SETTINGS_DIR = settings_dir
    window_module._SETTINGS_PATH = settings_path

    results.check(
        "missing settings file reads as an empty mapping",
        window_module._read_settings() == {},
    )

    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path.write_text('["not", "a", "mapping"]', encoding="utf-8")
    results.check(
        "valid non-object JSON is ignored",
        window_module._read_settings() == {},
    )
    settings_path.write_text("{broken", encoding="utf-8")
    results.check(
        "malformed JSON is ignored",
        window_module._read_settings() == {},
    )
    settings_path.write_text(
        json.dumps({"last_model": "model-a", "keep": "value"}),
        encoding="utf-8",
    )
    results.check(
        "valid settings objects are returned intact",
        window_module._read_settings()
        == {"last_model": "model-a", "keep": "value"},
    )

    class ReadFailurePath:
        def is_file(self) -> bool:
            return True

        def read_text(self, *, encoding: str) -> str:
            raise OSError("forced read failure")

    window_module._SETTINGS_PATH = ReadFailurePath()
    results.check(
        "settings read failures are ignored",
        window_module._read_settings() == {},
    )

    class TypeFailurePath:
        def is_file(self) -> bool:
            return True

        def read_text(self, *, encoding: str):
            return object()

    window_module._SETTINGS_PATH = TypeFailurePath()
    results.check(
        "settings read type failures are ignored",
        window_module._read_settings() == {},
    )

    window_module._SETTINGS_PATH = settings_path
    window_module._write_settings({"unicode": "✓", "nested": {"value": 1}})
    written = settings_path.read_text(encoding="utf-8")
    results.check(
        "settings writes are UTF-8 JSON objects with a trailing newline",
        written.endswith("\n")
        and json.loads(written) == {"unicode": "✓", "nested": {"value": 1}},
    )

    class WriteFailurePath:
        def write_text(self, *_args, **_kwargs) -> None:
            raise OSError("forced write failure")

    window_module._SETTINGS_PATH = WriteFailurePath()
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        window_module._write_settings({"last_model": "model-a"})
    results.check(
        "settings write failures are reported and suppressed",
        "settings save failed: forced write failure" in captured.getvalue(),
        captured.getvalue().strip(),
    )

    window_module._SETTINGS_PATH = settings_path
    for value, expected, label in (
        (None, None, "missing last_model returns None"),
        (7, None, "non-string last_model returns None"),
        ("", None, "empty last_model returns None"),
        ("   ", None, "whitespace-only last_model returns None"),
        ("  model-b  ", "  model-b  ", "nonblank last_model is returned untrimmed"),
    ):
        settings_path.write_text(
            json.dumps({"last_model": value}),
            encoding="utf-8",
        )
        actual = window_module._load_last_model()
        results.check(label, actual == expected, repr(actual))

    settings_path.write_text(
        json.dumps({"last_model": "same", "keep": "value"}),
        encoding="utf-8",
    )
    before = settings_path.read_text(encoding="utf-8")
    window_module._save_last_model("")
    window_module._save_last_model("   ")
    results.check(
        "empty and whitespace-only saves are no-ops",
        settings_path.read_text(encoding="utf-8") == before,
    )
    window_module._save_last_model("same")
    results.check(
        "saving the exact existing model is a no-op",
        settings_path.read_text(encoding="utf-8") == before,
    )
    window_module._save_last_model("  changed:model  ")
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    results.check(
        "saving a changed model preserves other keys and does not trim",
        saved == {"last_model": "  changed:model  ", "keep": "value"},
        repr(saved),
    )

    startup_cases = (
        ([], "model-a", 0, "empty model list selects index zero"),
        (["model-a", "model-b"], None, 0, "missing preference selects index zero"),
        (["model-a", "model-b"], "model-b", 1, "exact preference wins"),
        (
            ["model-a:8b", "model-a:latest"],
            "model-a:latest",
            1,
            "exact tagged preference wins over an earlier soft match",
        ),
        (
            ["other:latest", "model-a:8b", "model-a:latest"],
            "model-a:q4",
            1,
            "tag drift soft-matches the first installed base name",
        ),
        (
            ["model-a", "model-b"],
            "missing",
            0,
            "uninstalled preference falls back to index zero",
        ),
    )
    for models, preferred, expected, label in startup_cases:
        actual = window_module._pick_startup_model(models, preferred)
        results.check(label, actual == expected, str(actual))

    # Leave the production globals pointed at this test's isolated files for
    # the real ChatSidebar model-load/persistence checks below.
    window_module._SETTINGS_DIR = settings_dir
    window_module._SETTINGS_PATH = settings_path


def characterize_composer_geometry(results: Results, win: ChatSidebar) -> None:
    """Lock down the complete Phase-4 composer-geometry extraction surface."""
    print("\n[0b] Composer geometry characterization", flush=True)

    class FakeSurface:
        def __init__(self) -> None:
            self.connections: list[tuple[str, object]] = []

        def connect(self, signal: str, callback) -> int:
            self.connections.append((signal, callback))
            return len(self.connections)

    class HookOwner:
        def __init__(self) -> None:
            self.surface = None
            self.apply_calls = 0
            self._composer_layout_hooked = False
            self._surface_provider = lambda: self.surface

        def _apply_composer_height(self) -> None:
            self.apply_calls += 1

    hook_owner = HookOwner()
    ComposerGeometry._hook_composer_surface_layout(hook_owner)
    results.check(
        "surface hook retries when no surface is available",
        hook_owner._composer_layout_hooked is False and hook_owner.apply_calls == 0,
    )
    surface = FakeSurface()
    hook_owner.surface = surface
    ComposerGeometry._hook_composer_surface_layout(hook_owner)
    results.check(
        "surface hook connects one layout callback and marks itself hooked",
        hook_owner._composer_layout_hooked
        and [signal for signal, _callback in surface.connections] == ["layout"],
    )
    results.check(
        "surface hook immediately reapplies composer height",
        hook_owner.apply_calls == 1,
        str(hook_owner.apply_calls),
    )
    ComposerGeometry._hook_composer_surface_layout(hook_owner)
    results.check(
        "surface hook is idempotent after connection",
        len(surface.connections) == 1 and hook_owner.apply_calls == 1,
    )
    surface.connections[0][1](surface)
    results.check(
        "surface layout events reapply composer height",
        hook_owner.apply_calls == 2,
        str(hook_owner.apply_calls),
    )

    class LineLayout:
        def __init__(self, height: int) -> None:
            self.height = height

        def get_pixel_size(self) -> tuple[int, int]:
            return 10, self.height

    class LineInput:
        def __init__(self, *, height: int = 25, fail: bool = False) -> None:
            self.height = height
            self.fail = fail

        def create_pango_layout(self, _text: str) -> LineLayout:
            if self.fail:
                raise RuntimeError("forced layout failure")
            return LineLayout(self.height)

        def get_pixels_above_lines(self) -> int:
            return 1

        def get_pixels_below_lines(self) -> int:
            return 2

    no_line_input = type("NoLineInput", (), {"input": None})()
    results.check(
        "line height falls back to 22px without an input widget",
        ComposerGeometry._composer_line_height_px(no_line_input) == 22,
    )
    measured_line = type("MeasuredLine", (), {"input": LineInput()})()
    results.check(
        "line height includes Pango height and line spacing",
        ComposerGeometry._composer_line_height_px(measured_line) == 28,
    )
    minimum_line = type(
        "MinimumLine",
        (),
        {"input": LineInput(height=10)},
    )()
    results.check(
        "line height is clamped to an 18px minimum",
        ComposerGeometry._composer_line_height_px(minimum_line) == 18,
    )
    failed_line = type("FailedLine", (), {"input": LineInput(fail=True)})()
    results.check(
        "line height falls back to 22px when measurement fails",
        ComposerGeometry._composer_line_height_px(failed_line) == 22,
    )

    class WindowGeometry:
        def __init__(
            self,
            height: int,
            default_height: int = window_module.DEFAULT_HEIGHT,
            *,
            height_fails: bool = False,
            default_fails: bool = False,
        ) -> None:
            self.height = height
            self.default_height = default_height
            self.height_fails = height_fails
            self.default_fails = default_fails
            self._height_provider = self.get_height
            self._default_size_provider = self.get_default_size
            self._fallback_window_height = window_module.DEFAULT_HEIGHT

        def get_height(self) -> int:
            if self.height_fails:
                raise RuntimeError("forced height failure")
            return self.height

        def get_default_size(self) -> tuple[int, int]:
            if self.default_fails:
                raise RuntimeError("forced default-size failure")
            return 780, self.default_height

    results.check(
        "short current windows use the compact six-line cap",
        ComposerGeometry._composer_max_visible_lines(WindowGeometry(500))
        == window_module.COMPOSER_COMPACT_MAX_LINES,
    )
    results.check(
        "tall current windows use the normal eight-line cap",
        ComposerGeometry._composer_max_visible_lines(WindowGeometry(700))
        == window_module.COMPOSER_MAX_LINES,
    )
    results.check(
        "unallocated windows fall back to their short default height",
        ComposerGeometry._composer_max_visible_lines(WindowGeometry(0, 500))
        == window_module.COMPOSER_COMPACT_MAX_LINES,
    )
    results.check(
        "zero default-window height falls back to DEFAULT_HEIGHT",
        ComposerGeometry._composer_max_visible_lines(WindowGeometry(0, 0))
        == window_module.COMPOSER_MAX_LINES,
    )
    results.check(
        "window-height provider failures fall back to DEFAULT_HEIGHT",
        ComposerGeometry._composer_max_visible_lines(
            WindowGeometry(0, height_fails=True, default_fails=True)
        )
        == window_module.COMPOSER_MAX_LINES,
    )

    class WidthProvider:
        def __init__(self, width: int) -> None:
            self.width = width

        def get_width(self) -> int:
            return self.width

    class MeasureInput:
        def __init__(
            self,
            width: int,
            natural_height: int,
            *,
            fail: bool = False,
        ) -> None:
            self.width = width
            self.natural_height = natural_height
            self.fail = fail
            self.measured_widths: list[int] = []

        def get_width(self) -> int:
            return self.width

        def measure(self, orientation, width: int) -> tuple[int, int, int, int]:
            if self.fail:
                raise RuntimeError("forced content measurement failure")
            self.measured_widths.append(width)
            assert orientation == Gtk.Orientation.VERTICAL
            return 1, self.natural_height, -1, -1

    no_content_input = type(
        "NoContentInput",
        (),
        {"input": None, "_input_scroll": None},
    )()
    results.check(
        "content height falls back to 36px without an input widget",
        ComposerGeometry._composer_content_height_px(no_content_input) == 36,
    )
    own_width_input = MeasureInput(250, 80)
    own_width_owner = type(
        "OwnWidthOwner",
        (),
        {"input": own_width_input, "_input_scroll": WidthProvider(320)},
    )()
    results.check(
        "content measurement uses the allocated input width",
        ComposerGeometry._composer_content_height_px(own_width_owner) == 80
        and own_width_input.measured_widths == [250],
    )
    scroll_width_input = MeasureInput(0, 70)
    scroll_width_owner = type(
        "ScrollWidthOwner",
        (),
        {"input": scroll_width_input, "_input_scroll": WidthProvider(320)},
    )()
    results.check(
        "content measurement falls back to the scroller width",
        ComposerGeometry._composer_content_height_px(scroll_width_owner) == 70
        and scroll_width_input.measured_widths == [320],
    )
    default_width_input = MeasureInput(0, 0)
    default_width_owner = type(
        "DefaultWidthOwner",
        (),
        {"input": default_width_input, "_input_scroll": WidthProvider(0)},
    )()
    results.check(
        "content measurement falls back to 400px and floors natural height at one",
        ComposerGeometry._composer_content_height_px(default_width_owner) == 1
        and default_width_input.measured_widths == [400],
    )
    failed_content_owner = type(
        "FailedContentOwner",
        (),
        {
            "input": MeasureInput(250, 80, fail=True),
            "_input_scroll": WidthProvider(320),
        },
    )()
    results.check(
        "content height falls back to 36px when measurement fails",
        ComposerGeometry._composer_content_height_px(failed_content_owner) == 36,
    )

    class MarginInput:
        def get_top_margin(self) -> int:
            return 8

        def get_bottom_margin(self) -> int:
            return 8

    class SizeTarget:
        def __init__(self) -> None:
            self.requests: list[tuple[int, int]] = []

        def set_size_request(self, width: int, height: int) -> None:
            self.requests.append((width, height))

    class GeometryScroll(SizeTarget):
        def __init__(self) -> None:
            super().__init__()
            self.policies: list[tuple[Gtk.PolicyType, Gtk.PolicyType]] = []
            self.min_heights: list[int] = []
            self.max_heights: list[int] = []
            self.parent = SizeTarget()

        def set_policy(self, horizontal, vertical) -> None:
            self.policies.append((horizontal, vertical))

        def set_min_content_height(self, height: int) -> None:
            self.min_heights.append(height)

        def set_max_content_height(self, height: int) -> None:
            self.max_heights.append(height)

        def get_parent(self) -> SizeTarget:
            return self.parent

    class ApplyOwner:
        def __init__(self, content_height: int) -> None:
            self.input = MarginInput()
            self._input_scroll = GeometryScroll()
            self.content_height = content_height
            self.sync_calls: list[tuple[int, int]] = []

        def _composer_line_height_px(self) -> int:
            return 20

        def _composer_max_visible_lines(self) -> int:
            return 6

        def _composer_content_height_px(self) -> int:
            return self.content_height

        def _align_callback(
            self,
            *,
            content_h: int,
            min_h: int,
        ) -> None:
            self.sync_calls.append((content_h, min_h))

    missing_geometry = type(
        "MissingGeometry",
        (),
        {"input": None, "_input_scroll": None},
    )()
    ComposerGeometry._apply_composer_height(missing_geometry)
    results.check(
        "height application is a no-op until both widgets exist",
        missing_geometry.input is None and missing_geometry._input_scroll is None,
    )

    short_owner = ApplyOwner(20)
    ComposerGeometry._apply_composer_height(short_owner)
    short_scroll = short_owner._input_scroll
    results.check(
        "short content uses the 36px minimum without a scrollbar",
        short_scroll.policies
        == [(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)]
        and short_scroll.min_heights == [36]
        and short_scroll.max_heights == [136]
        and short_scroll.requests == [(-1, 36)]
        and short_scroll.parent.requests == [(-1, 36)]
        and short_owner.sync_calls == [(20, 36)],
    )

    medium_owner = ApplyOwner(80)
    ComposerGeometry._apply_composer_height(medium_owner)
    results.check(
        "medium content uses its natural height without a scrollbar",
        medium_owner._input_scroll.min_heights == [80]
        and medium_owner._input_scroll.policies
        == [(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)],
    )

    tall_owner = ApplyOwner(200)
    ComposerGeometry._apply_composer_height(tall_owner)
    results.check(
        "over-cap content is clamped and enables automatic vertical scrolling",
        tall_owner._input_scroll.min_heights == [136]
        and tall_owner._input_scroll.max_heights == [136]
        and tall_owner._input_scroll.policies
        == [(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)]
        and tall_owner.sync_calls == [(200, 36)],
    )

    class FakeLabel:
        def __init__(self) -> None:
            self.visible = False
            self.text = ""
            self.classes: set[str] = set()
            self.tooltip = ""

        def set_visible(self, visible: bool) -> None:
            self.visible = visible

        def set_text(self, text: str) -> None:
            self.text = text

        def add_css_class(self, name: str) -> None:
            self.classes.add(name)

        def remove_css_class(self, name: str) -> None:
            self.classes.discard(name)

        def set_tooltip_text(self, text: str) -> None:
            self.tooltip = text

    label = FakeLabel()
    counter_owner = type(
        "CounterOwner",
        (),
        {"_composer_char_label": label},
    )()
    threshold = int(
        window_module.COMPOSER_CHAR_LIMIT
        * window_module.COMPOSER_COUNTER_SHOW_RATIO
    )
    ComposerGeometry._update_composer_char_counter(counter_owner, threshold - 1)
    results.check(
        "character counter stays hidden below the warning threshold",
        label.visible is False,
    )
    ComposerGeometry._update_composer_char_counter(counter_owner, threshold)
    results.check(
        "character counter appears at the threshold with normal styling",
        label.visible
        and label.text
        == f"{threshold:,} / {window_module.COMPOSER_CHAR_LIMIT:,}"
        and "warning" not in label.classes
        and label.tooltip
        == (
            "Hard safety limit is "
            f"{window_module.COMPOSER_CHAR_LIMIT:,} characters"
        ),
    )
    ComposerGeometry._update_composer_char_counter(
        counter_owner,
        window_module.COMPOSER_CHAR_LIMIT,
    )
    results.check(
        "character counter warns at the hard cap",
        label.text
        == (
            f"{window_module.COMPOSER_CHAR_LIMIT:,} / "
            f"{window_module.COMPOSER_CHAR_LIMIT:,}"
        )
        and "warning" in label.classes
        and label.tooltip == "Character safety limit reached",
    )

    class InsertBuffer:
        def __init__(self, count: int) -> None:
            self.count = count
            self.stopped: list[str] = []
            self.inserted: list[tuple[object, str]] = []

        def get_char_count(self) -> int:
            return self.count

        def stop_emission_by_name(self, name: str) -> None:
            self.stopped.append(name)

        def insert(self, location, text: str) -> None:
            self.inserted.append((location, text))
            self.count += len(text)

    class InsertOwner:
        def __init__(self, truncating: bool = False) -> None:
            self._composer_truncating = truncating
            self.counter_updates: list[int] = []

        def _update_composer_char_counter(self, count: int) -> None:
            self.counter_updates.append(count)

    guarded_owner = InsertOwner(truncating=True)
    guarded_buffer = InsertBuffer(10)
    ComposerGeometry._on_composer_insert_text(
        guarded_owner,
        guarded_buffer,
        "loc",
        "ignored",
        7,
    )
    ComposerGeometry._on_composer_insert_text(
        InsertOwner(),
        guarded_buffer,
        "loc",
        "",
        0,
    )
    results.check(
        "insert handler ignores reentrant and empty insertions",
        guarded_buffer.stopped == [] and guarded_buffer.inserted == [],
    )

    full_owner = InsertOwner()
    full_buffer = InsertBuffer(window_module.COMPOSER_CHAR_LIMIT)
    ComposerGeometry._on_composer_insert_text(
        full_owner,
        full_buffer,
        "loc",
        "x",
        1,
    )
    results.check(
        "insertions at the hard cap are stopped and refresh the counter",
        full_buffer.stopped == ["insert-text"]
        and full_buffer.inserted == []
        and full_owner.counter_updates
        == [window_module.COMPOSER_CHAR_LIMIT],
    )

    paste_owner = InsertOwner()
    paste_buffer = InsertBuffer(window_module.COMPOSER_CHAR_LIMIT - 3)
    ComposerGeometry._on_composer_insert_text(
        paste_owner,
        paste_buffer,
        "loc",
        "abcdef",
        6,
    )
    results.check(
        "oversized pastes are clamped and the reentrancy guard is restored",
        paste_buffer.stopped == ["insert-text"]
        and paste_buffer.inserted == [("loc", "abc")]
        and paste_owner._composer_truncating is False,
    )

    fitting_owner = InsertOwner()
    fitting_buffer = InsertBuffer(10)
    ComposerGeometry._on_composer_insert_text(
        fitting_owner,
        fitting_buffer,
        "loc",
        "fits",
        4,
    )
    results.check(
        "in-range insertions are left to the default buffer handler",
        fitting_buffer.stopped == [] and fitting_buffer.inserted == [],
    )

    class ChangedBuffer:
        def __init__(self, text: str) -> None:
            self.text = text
            self.deletions: list[tuple[int, int]] = []

        def get_char_count(self) -> int:
            return len(self.text)

        def get_iter_at_offset(self, offset: int) -> int:
            return offset

        def get_end_iter(self) -> int:
            return len(self.text)

        def delete(self, start: int, end: int) -> None:
            self.deletions.append((start, end))
            self.text = self.text[:start] + self.text[end:]

        def get_start_iter(self) -> int:
            return 0

        def get_text(self, start: int, end: int, _include_hidden: bool) -> str:
            return self.text[start:end]

    class VisibilityTarget:
        def __init__(self) -> None:
            self.visible = None

        def set_visible(self, visible: bool) -> None:
            self.visible = visible

    class ChangedOwner:
        def __init__(self, truncating: bool = False) -> None:
            self._composer_truncating = truncating
            self._placeholder = VisibilityTarget()
            self.counter_updates: list[int] = []
            self.apply_calls = 0
            self.idle_align_calls = 0

        def _update_composer_char_counter(self, count: int) -> None:
            self.counter_updates.append(count)

        def _apply_composer_height(self) -> None:
            self.apply_calls += 1

        def _align_callback(self) -> bool:
            self.idle_align_calls += 1
            return False

    guarded_changed_owner = ChangedOwner(truncating=True)
    guarded_changed_buffer = ChangedBuffer("ignored")
    ComposerGeometry._on_buffer_changed(
        guarded_changed_owner,
        guarded_changed_buffer,
    )
    results.check(
        "changed handler ignores reentrant buffer mutations",
        guarded_changed_owner.counter_updates == []
        and guarded_changed_owner.apply_calls == 0,
    )

    over_limit_owner = ChangedOwner()
    over_limit_buffer = ChangedBuffer(
        "x" * (window_module.COMPOSER_CHAR_LIMIT + 5)
    )
    ComposerGeometry._on_buffer_changed(over_limit_owner, over_limit_buffer)
    pump(0.05)
    results.check(
        "changed handler deletes text beyond the hard cap and restores its guard",
        len(over_limit_buffer.text) == window_module.COMPOSER_CHAR_LIMIT
        and over_limit_buffer.deletions
        == [
            (
                window_module.COMPOSER_CHAR_LIMIT,
                window_module.COMPOSER_CHAR_LIMIT + 5,
            )
        ]
        and over_limit_owner._composer_truncating is False,
    )
    results.check(
        "changed handler updates placeholder, counter, height, and idle alignment",
        over_limit_owner._placeholder.visible is False
        and over_limit_owner.counter_updates
        == [window_module.COMPOSER_CHAR_LIMIT]
        and over_limit_owner.apply_calls == 1
        and over_limit_owner.idle_align_calls == 1,
    )

    empty_owner = ChangedOwner()
    ComposerGeometry._on_buffer_changed(empty_owner, ChangedBuffer(""))
    pump(0.05)
    results.check(
        "empty changed buffers show the placeholder and report zero characters",
        empty_owner._placeholder.visible is True
        and empty_owner.counter_updates == [0]
        and empty_owner.apply_calls == 1
        and empty_owner.idle_align_calls == 1,
    )

    results.check(
        "composer controller owns its private flags instead of the window",
        win._composer_geometry is not None
        and win._composer_geometry._composer_truncating is False
        and win._composer_geometry._composer_layout_hooked is True
        and not hasattr(win, "_composer_truncating")
        and not hasattr(win, "_composer_layout_hooked"),
    )
    results.check(
        "realized composer connects its surface-layout hook",
        win._composer_geometry is not None
        and win._composer_geometry._composer_layout_hooked is True,
    )
    initial_request = win._input_scroll.get_size_request()
    results.check(
        "construction applies an initial composer height",
        win._input_scroll.get_min_content_height() >= 36
        and win._input_scroll.get_max_content_height()
        >= win._input_scroll.get_min_content_height()
        and initial_request[1] >= 36,
        str(initial_request),
    )

    map_calls: list[str] = []
    original_apply_height = win._composer_geometry._apply_composer_height
    win._composer_geometry._apply_composer_height = (
        lambda *_args: map_calls.append("map")
    )
    map_error = ""
    try:
        win.emit("map")
    except Exception as exc:  # noqa: BLE001
        map_error = repr(exc)
    finally:
        win._composer_geometry._apply_composer_height = original_apply_height
    results.check(
        "window map signal is wired to composer-height reapplication",
        map_calls == ["map"] and not map_error,
        map_error or repr(map_calls),
    )

    real_buffer = win.input.get_buffer()
    real_buffer.set_text("")
    pump(0.05)
    results.check(
        "real changed signal shows the placeholder for an empty buffer",
        win._placeholder.get_visible() is True,
    )
    real_buffer.set_text("hello")
    pump(0.05)
    results.check(
        "real changed signal hides the placeholder for nonempty text",
        win._placeholder.get_visible() is False,
    )

    real_buffer.set_text("x" * window_module.COMPOSER_CHAR_LIMIT)
    pump(0.05)
    results.check(
        "real changed signal presents the hard-cap counter warning",
        real_buffer.get_char_count() == window_module.COMPOSER_CHAR_LIMIT
        and win._composer_char_label.get_visible()
        and win._composer_char_label.has_css_class("warning"),
    )

    real_buffer.set_text("x" * (window_module.COMPOSER_CHAR_LIMIT - 2))
    end = real_buffer.get_end_iter()
    real_buffer.insert(end, "wxyz")
    pump(0.05)
    real_text = real_buffer.get_text(
        real_buffer.get_start_iter(),
        real_buffer.get_end_iter(),
        False,
    )
    results.check(
        "real insert-text signal clamps an oversized paste at the hard cap",
        real_buffer.get_char_count() == window_module.COMPOSER_CHAR_LIMIT
        and real_text.endswith("wx"),
    )

    real_buffer.set_text("")
    pump(0.05)
    results.check(
        "composer test restores the real buffer to its empty startup state",
        real_buffer.get_char_count() == 0
        and win._placeholder.get_visible() is True
        and win._composer_char_label.get_visible() is False,
    )


def main() -> int:
    results = Results()

    TMP = Path(tempfile.mkdtemp(prefix="cb-sidebar-interactions-"))
    os.environ["CHICKENBUTT_DB"] = str(TMP / "db.sqlite")
    os.environ["XDG_CONFIG_HOME"] = str(TMP / "config")
    os.environ["XDG_DATA_HOME"] = str(TMP / "data")

    settings_dir = TMP / "config" / "chickenbutt"
    settings_path = settings_dir / "settings.json"
    characterize_settings(results, settings_dir, settings_path)

    # Seed a stale settings file with the old, no-longer-read sidebar_open
    # key set to true, BEFORE constructing any window — proves it's ignored
    # rather than merely untested.
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
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
    characterize_composer_geometry(results, win)

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
    # settle first — otherwise our explicit _refresh_models() call below
    # just no-ops against the in-flight real one (_loading_model guard) and
    # we'd observe the real model instead of the fake ones we're about to
    # substitute.
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
