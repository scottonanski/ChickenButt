# ChickenButt — handoff for next session

**Updated:** 2026-07-22 (post release-hardening session — see "This session" below)  
**What it is:** GNOME desktop chat client for local **Ollama** (tray app, Adwaita chrome).  
**Product aim:** be **the nicest lightweight GNOME client for Ollama** — simple, fast, native-looking, immediately understandable — **not** a smaller clone of Open WebUI or LM Studio.

ChickenButt wins on **focus and feel**, not feature count.  
**PMM (Persistent Mind Model):** out of band — do **not** integrate unless the user explicitly asks.

---

## This session (2026-07-22): release hardening, not features

The prior snapshot of this file described a feature-complete-feeling prototype. Since then the project went through an **audit → fix → verify → commit** cycle focused entirely on correctness and performance, not new product surface. Read this section before touching generation, streaming, or the transcript restore path — it explains *why* the code looks the way it does now, not just what it does.

### Landed (in commit order)

1. **`a6fe621`** — Code-block resize instability. Root cause: `pre code` used `white-space: pre-wrap`, so `scrollHeight` (used to decide collapse state) was width-dependent — resizing the window changed which lines wrapped, which changed the collapse decision, which changed the card height. Fixed to `white-space: pre` + horizontal scroll (`overflow-x: auto; min-width: 0` on the flex child). Streaming and finalized code cards share the same rule (`.streaming-code` only adds an outline).
2. **`b99a5fe`** — **Cross-chat generation corruption** (the big one). `switch_conversation`/`new_chat`/`delete_conversation` all stopped a running stream and *immediately* reset the shared `_stop_stream` flag back to `False`, un-cancelling it, then let a new generation start. The old stream's worker thread could keep running and its completion callback — in WebKit mode, `still_current()` returned `True` unconditionally — would persist its output into whatever conversation was now active. Fixed with stream-owned state: a monotonic `_stream_generation` counter + a per-stream `threading.Event` (`_active_stream_cancel`), captured conversation id/model at stream start, `_invalidate_active_stream()` as the one choke point for switch/new/delete. Manual Stop only cancels (keeps the partial reply); switching invalidates (discards it). Regression: `scripts/test_generation_lifecycle.py`.
3. **`406df07`** — Tiny standalone fix for a flaky race in that new test (waits for cold-start model probe to settle before driving switch scenarios).
4. **`62b207d`** — **Uninterruptible stalled stream.** `chat_stream` had no socket timeout and only checked `should_stop` between `readline()` calls, so a connection that stayed open but went quiet couldn't be cancelled — Stop just hung until data arrived. Rewritten on `http.client` (not `urlopen`, so the code holds `conn.sock` directly rather than reaching into `urlopen`'s response internals) with a watcher thread that shuts the socket down on cancellation, waking a blocked `readline()` immediately. A `stream_finished` event distinguishes "woken to clean up" from "woken because the user actually cancelled," so normal completion doesn't race a spurious shutdown. `saw_done` tracks whether Ollama's `done:true` ever arrived, so a graceful-but-premature close (which looks identical at the socket level to our own cancellation shutdown) still raises `OllamaError` instead of silently succeeding. Regression: `scripts/test_stream_cancellation.py` (real stub-server sockets, no mocking).
5. **`81f666c`** — **Restoration scrolling.** Measured (not guessed — see profiling below) that `conversation_reset` called `scrollIfPinned()` once per restored message, forcing a `scrollHeight` layout read that grows with total DOM size — O(n²) for the whole restore. Added a local `deferScroll` option on `addMessage()`; only the restore loop sets it, then scrolls once after the batch. 1000-message restore: mixed ~1926–2169ms → 590ms, code-heavy ~2311–2542ms → 905ms, and — more importantly — per-message cost is now flat instead of doubling across the batch (restoration is linear again, not super-linear). Regression: `scripts/test_restore_scroll.py` (spies on `#root`'s real `scrollTop` setter via injected JS, no mocking).
6. **`467017d`** — **Batch `wireCodeUi()` during restoration.** The same ablation study behind item 5 isolated a second, independent restoration cost: `wireCodeUi()`'s per-message `requestAnimationFrame` code-height measurement, run once per restored message over an ever-growing DOM. Added a `deferWire` option on `addMessage()` — the restore loop sets it (skipping the per-message call), then calls `wireCodeUi(messagesEl)` once on the whole container after the batch is appended. `wireCodeCopy`/`wireCodeExpand` already operate via `querySelectorAll`, so one pass over the container correctly wires every restored code block; markdown rendering and `highlightAllIn()` are untouched, and live (non-restore) messages still wire their own code UI immediately. Code-heavy 1000-message restore: 4760ms baseline → 2949ms with the scroll fix (item 5) alone → 2485ms with both fixes landed. Regression: `scripts/test_wire_code_ui_batch.py`.

Each of the above is genuinely single-purpose — reviewed and split deliberately (e.g. `406df07` was pulled out of what became `62b207d` specifically so an unrelated test-stability fix wouldn't dilute the cancellation commit).

### Performance audit — instrumentation is uncommitted, on purpose

A measurement-only profiling pass (`CHICKENBUTT_PROFILE=1`, inert otherwise) was built to find the *next* bottleneck instead of guessing:

- **`profiling.py`** (new, tiny, untracked) — Python-side `mark(name)`, no-ops unless the env var is set.
- **`window.py` / `main.py` / `transcript_view.py`** — scattered `profiling.mark(...)` calls at lifecycle milestones. Never committed to any branch, on purpose, pending a decision on whether/how to land them — check `git log -- window.py main.py transcript_view.py` if you need to know whether that's changed, since this file can't track anyone's local working-tree or stash state.
- **`web/app.js`** — a matching JS-side profiler (`mark`/`markRaf`, gated on a `?profile=1` URL flag) instrumenting `finalizeStream()` stages and the streaming/restore bridge. **Not currently in the working tree** — it was deliberately kept out of the `81f666c` commit (see below) and would need to be re-added from scratch if wanted again; it is not saved anywhere.
- **`scripts/profile_startup.py`**, **`scripts/profile_runtime.py`**, **`scripts/profile_ablation.py`** — benchmark drivers (untracked). Not part of the test suite; run manually.

**Why `web/app.js` doesn't currently have the JS profiler**: the `81f666c` commit needed to be *only* the scrolling fix. Since the profiler and the fix were both live edits to the same file, the clean way to isolate the commit was to rebuild `app.js` from `git show HEAD:web/app.js` (the true untouched baseline) plus just the two fix lines, then commit that — which means the JS profiler that existed moments before is gone from the working tree now, not merely uncommitted. If you want to re-run `profile_runtime.py`'s streaming/finalize/restore benchmarks, the JS-side `mark()`/`markRaf()` calls and the `?profile=1` handling in `web/app.js` need to be re-added first (they're straightforward — see the pattern already sitting in `window.py`'s `profiling.mark(...)` calls for what the JS side mirrored).

**Findings that still matter, even without re-adding the JS profiler:**
- WebKit's own page-load cost (~2.1–2.4s) dominates *startup*, is bimodal (first launch in a fresh cache vs. a warm one differ ~4×), and is not something ChickenButt's code controls.
- Ordinary prose streaming is fine; the existing ~33ms batching absorbs chunk count well regardless of how many chunks arrive.
- Syntax highlighting is the dominant *single-stage* cost wherever code is present (both live streaming DOM-update cost and `finalizeStream`'s stage breakdown).
- An ablation study (`scripts/profile_ablation.py`, temporary — reverted after use, not currently reflected in `app.js`) isolated that per-message `scrollIfPinned()` was the dominant restoration cost (fixed in `81f666c`, item 5) and that batching `wireCodeUi()`'s per-message `requestAnimationFrame` code-height measurement was a *second, independent* win specifically for code-heavy histories (fixed in `467017d`, item 6 — see numbers there). `highlightAllIn()` batching showed no meaningful effect and isn't worth doing.

### Performance audit — closed out

Every defect the audit set out to fix has landed: the stalled-open HTTP stream (`62b207d`), the restoration scroll cost (`81f666c`, item 5), and the restoration `wireCodeUi` cost (`467017d`, item 6). The only item left from the audit is long-term and speculative: transcript virtualization or incremental history loading, only worth doing if a real 1000+ message code-heavy history is still measurably slow in practice — ~2.5s was the last measured floor with both bounded fixes landed, and nothing currently indicates that's a problem users hit.

### Security hardening (landed the same day, a separate initiative from the performance audit)

Three commits harden the WebKit transcript against untrusted content — relevant now that model output, and eventually cloud models / attachments / pasted web content, reach it:

- **`0f50cf1`** — **Markdown sanitization.** `renderMarkdown()` used to pipe `marked.parse()` output straight into `innerHTML` with no sanitizer. Rendered output now passes through vendored DOMPurify (`web/vendor/purify.min.js`) first. Regression: `scripts/test_markdown_sanitization.py` (84 checks).
- **`b4bd7d1`** — **WebKit navigation confinement.** `transcript_view.py` hooks `WebView`'s `decide-policy` signal (`_on_decide_policy`) so the embedded WebView can only ever display the local trusted transcript page. Exact navigation back to that trusted URI is allowed; everything else is blocked (`decision.ignore()`) except one narrow case — a genuine user-initiated, non-redirect navigation to an external http(s) URI, which is handed to the system's default application via `Gio.AppInfo.launch_default_for_uri` instead of being loaded in the WebView. `NEW_WINDOW_ACTION` is never allowed to load in-view either way, since this app never creates a second window to load it into. Regression: `scripts/test_web_navigation_policy.py` (56 checks).
- **`90965ca`** — **Strict CSP on the transcript WebView.** `transcript_view.py` constructs the `WebView` with a `default_content_security_policy` (`TRANSCRIPT_CSP`) that defaults every directive to `'none'` and only allows `'self'` for `script-src`/`style-src`/`img-src`. Regression: `scripts/test_web_content_security_policy.py` (53 checks).

All three regression tests are part of the standard suite — see "Quick health check" below.

### A gotcha worth remembering for anyone writing more benchmarks/tests

If you seed a conversation into the DB and then construct a fresh `ChatSidebar`, that seeded conversation is the "active" one, so `ChatSidebar.__init__`'s own `_restore_history()` will restore it at construction time. If your test/benchmark *also* explicitly calls `switch_conversation()` on the same conversation afterward (common when forcing a fresh measurement), you get **two** restores of the same data back-to-back, silently doubling every count and cost you measure. Fix: after seeding the target conversation, create one more, empty conversation (`store.create_conversation(...)`) so *it* is active at construction time, and your explicit `switch_conversation()` call is the only real restore. This bit both `profile_ablation.py` and an early draft of the restore-scroll test.

---

## Run

```bash
# Default — WebKit transcript
./run.sh

# Optional fallback — native GTK bubble renderer
CHICKENBUTT_TRANSCRIPT=native ./run.sh

# Regenerate tracked source icon assets (icons/hicolor, icons/tray) —
# source-asset generator only, never writes outside the repo tree
python3 scripts/generate-icons.py

# Regression (see "Quick health check" below for the full current list)
python3 scripts/smoke_gui.py              # ~25 checks — expect all PASS
python3 scripts/test_multichat.py
python3 scripts/test_message_actions.py
python3 scripts/test_ollama_health.py
```

| Item | Value |
|------|--------|
| App ID | `io.github.scottonanski.ChickenButt` (must match desktop entry) |
| Version | `0.1.0` |
| Desktop entry | Installed by Meson from `data/*.desktop.in` → `<prefix>/share/applications/io.github.scottonanski.ChickenButt.desktop` |
| SQLite DB | `~/.local/share/chickenbutt/conversations.db` (`CHICKENBUTT_DB` override) |
| Settings | `~/.config/chickenbutt/settings.json` (last model only — sidebar-open state is no longer persisted; the sidebar always starts closed) |

---

## Installed runtime layout (Meson) — private app dir, not a Python package

Bounded first packaging step, landed this session: a real, installable runtime via Meson. This is deliberately **not** pip/pipx/a Python package — ChickenButt depends on system GI typelibs (GTK4/Adwaita/WebKit), a local WebKit page, and vendored JS/Python, so the installed layout mirrors the source tree's existing relative-resource structure instead:

```text
<prefix>/bin/chickenbutt
<prefix>/<libdir>/chickenbutt/
    main.py, conversation_store.py, message_widgets.py, ollama_client.py,
    ollama_health.py, release_info.py, tray.py, transcript_view.py,
    window.py, x11_sidebar.py (dead code, unimported — see Repository map)
    web/**       (transcript page + vendored marked/DOMPurify/highlight.js)
    vendor/**    (vendored Python — mistune)
    icons/**     (private fallback icons)
```

This preserves every existing relative-resource lookup unmodified: `transcript_view.WEB_DIR` still resolves sibling `web/`, `message_widgets.py` still finds sibling `vendor/mistune` via its own `sys.path` insert, `web/index.html` still resolves `../icons/`, and `main.py`'s APP_DIR-relative icon fallbacks still work — because `<libdir>/chickenbutt/` has exactly the same internal shape as the repo root.

**Runtime Python files are an explicit allowlist in `meson.build`**, not a glob — this is what keeps the untracked, dev-only `profiling.py` (and anything else not named) out of the installed tree, on purpose.

```bash
# Build tools required (not part of the app's own runtime deps):
#   meson >=0.64, ninja — via system packages, or a throwaway venv:
#   python3 -m venv /tmp/bt && /tmp/bt/bin/pip install meson ninja

meson setup build --prefix="$HOME/.local"
meson install -C build
"$HOME/.local/bin/chickenbutt"             # launches normally
"$HOME/.local/bin/chickenbutt" --version   # → "ChickenButt 0.1.0", no window
```

`main.py --version` (and therefore `chickenbutt --version` / `./run.sh --version`) prints `{APP_NAME} {VERSION}` from `release_info.py` and returns before `Adw.init()` — no display/window needed.

**The installed launcher resolves `python3` from the runtime environment's own `PATH`** (`exec python3 '@PKGLIBDIR@/main.py' "$@"`), not the interpreter Meson happened to find at configure time. Meson itself is often run from a disposable build-tool venv (`find_program('python3')` in `meson.build` is only used for enumerating vendor files at configure time) — embedding `python3.full_path()` into the launcher would have permanently tied an installed ChickenButt to that venv, breaking the moment it's deleted. `scripts/test_installed_layout.py` proves this: it configures with a fake, uniquely-pathed `python3` wrapper first on `PATH`, confirms Meson actually used it, confirms it never appears anywhere in the generated launcher, deletes that fake venv entirely, and *then* confirms the installed `chickenbutt --version` still works.

**Not yet done, on purpose** (separate follow-up work): screenshot/release-history metadata in the AppStream file, a tagged 0.1.0 release, Flatpak manifest, CI.

Regression: `scripts/test_installed_layout.py` — does a real `meson setup`/`meson install` into a temporary prefix and runs the installed launcher from an unrelated directory. It builds from `git write-tree` + `git archive` (what would actually be committed), not the raw working directory — the working tree can carry uncommitted profiling instrumentation in `main.py` that would otherwise install a `main.py` requiring a `profiling` module that must never ship. Skips cleanly (exit 0, clear message) if `meson` isn't on `PATH`, so it doesn't block the rest of the suite on machines without it. **CI must install `meson`/`ninja` once CI exists — this test cannot remain silently skipped there.**

### Desktop integration (Meson) — app-grid entry, public icon, AppStream metadata

Meson now installs the pieces needed for ChickenButt to show up as a normal
GNOME application, not just a `chickenbutt` terminal command:

```text
<prefix>/share/applications/io.github.scottonanski.ChickenButt.desktop
<prefix>/share/icons/hicolor/scalable/apps/io.github.scottonanski.ChickenButt.svg
<prefix>/share/metainfo/io.github.scottonanski.ChickenButt.metainfo.xml
```

Canonical, tracked templates (Meson substitutes `@APP_ID@`/`@APP_NAME@` at
configure time, read from `release_info.py` via the same `python3`
`meson.build` already uses for vendor-file enumeration — configuration
fails clearly if that read fails, so there is no second, hand-maintained
copy of the app identity):

- `data/io.github.scottonanski.ChickenButt.desktop.in` — `Exec=chickenbutt` /
  `TryExec=chickenbutt` (unqualified — resolved via `PATH`, not baked to an
  absolute install path), `Icon=@APP_ID@`, `StartupWMClass=@APP_ID@`,
  `DBusActivatable=false` (no D-Bus activation was added).
- `data/io.github.scottonanski.ChickenButt.metainfo.xml.in` — id, licenses,
  developer, description, `<launchable type="desktop-id">`, `<provides>`
  binary, urls, OARS content rating. Deliberately **no** `<screenshots>` or
  `<releases>` — there is no tagged release or hosted screenshot yet, and
  fabricating either would be worse than omitting them.
- The public icon is the existing `icons/chickenbutt-dash-desktop-icon.svg`,
  installed (not regenerated) under `hicolor/scalable/apps/` renamed to
  `<APP_ID>.svg`. The private `icons/` runtime directory (used for the
  tray and in-tree fallbacks — see "Installed runtime layout" above) is
  untouched.
- `meson.build` calls `import('gnome').post_install(update_desktop_database:
  true, gtk_update_icon_cache: true)` so a real `meson install` refreshes
  the desktop/icon caches; this is scoped to whatever prefix was installed
  into, same as everything else here.
- `main.py`'s window-icon calls (`set_icon_name`, the `theme.has_icon(...)`
  check, and the fallback loop) all use `APP_ID` from `release_info` now,
  not a literal `"chickenbutt"` string — the private-file fallback paths
  themselves are unchanged.

**Retired, on purpose:** the old clone-bound install path — the tracked
root `io.github.scottonanski.ChickenButt.desktop` file and
`scripts/install-desktop-entry.py` (which wrote into
`~/.local/share/applications/` relative to wherever the repo happened to
be cloned) are both gone. `scripts/install-icons.py` is renamed to
**`scripts/generate-icons.py`** and is now a **source-asset generator
only** — it may still regenerate the tracked `icons/hicolor/` and
`icons/tray/` files from the SVG source, but every write into
`~/.local/share/icons` and every user icon-cache update was removed; it
must never touch `$HOME`. The public icon a user actually gets now comes
from `meson install`, not a separate helper script run against the
source tree.

Regression: `scripts/test_desktop_integration.py` (37 checks) — same
`git write-tree` + `git archive` clean-export pattern as
`test_installed_layout.py` (so profiling dirt in the working tree can't
leak into the installed files), then a real `meson setup`/`meson
install` into a temp prefix. Verifies the desktop file's filename/
`Exec`/`TryExec`/`Icon`/`StartupWMClass`/`DBusActivatable` and that it
has no leaked absolute paths; runs real `desktop-file-validate` and
`appstreamcli validate --no-net` against the installed files when those
tools are present (optional — see `DEPENDENCIES.md`), treating only
genuine errors as failures and explicitly surfacing (not silently
swallowing) the expected pre-release pedantic warnings
(`cid-contains-uppercase-letter`, `releases-info-missing`); checks the
SVG lands at exactly `<APP_ID>.svg` with no `chickenbutt.svg` alias;
checks the metainfo file's `<id>`, launchable, binary provider, licenses,
developer/url/OARS elements, and that no screenshots/releases were
fabricated; confirms `main.py` uses `APP_ID` for the window icon;
confirms the old root `.desktop` file and `install-desktop-entry.py` are
both absent and `generate-icons.py` has no home-directory install path;
and re-runs `test_installed_layout.py` as a subprocess at the end to
prove the private-runtime install still passes every one of its own
assertions unchanged. Skips cleanly if `meson` isn't on `PATH`, same as
`test_installed_layout.py`.

### System dependencies and reproducible installation

Canonical dependency list: **[DEPENDENCIES.md](DEPENDENCIES.md)** — four categories (required runtime libraries, build/install tools, optional integration, external Ollama service), why `dasbus` is required (not optional — `tray.py` imports it unconditionally for the StatusNotifier D-Bus interface), why `GtkSource 5` only affects the optional native transcript fallback, and verified Fedora 43/44 / Ubuntu 24.04+ package names.

```bash
python3 scripts/check_dependencies.py            # required runtime deps; optional/external reported, never fail the exit code
python3 scripts/check_dependencies.py --build     # also requires git/meson/ninja
```

Stdlib-only until it starts probing; no GTK init, no window, no `DISPLAY`/`WAYLAND_DISPLAY`/D-Bus session requirement, no distro detection, no package-manager execution, no pip invocation. Regression: `scripts/test_dependency_declaration.py` (headless run, shadowed `gi`/`dasbus` modules that fail clearly, a too-old fake `meson` correctly rejected by the version gate, GtkSource/Ollama absence never fail it, README/DEPENDENCIES.md content checks).

README now documents the full reproducible source-install path (`meson setup build --prefix="$HOME/.local"` → `meson install -C build` → `chickenbutt --version`), rebuilding (`meson setup --reconfigure`), uninstalling (`ninja -C build uninstall`), and running Ollama — and now that the desktop entry/public icon/AppStream metadata are installed by Meson (see "Desktop integration" above), it says installed ChickenButt should appear in the GNOME app grid, while noting screenshot/release metadata and Flatpak packaging remain unfinished.

### Stuck launch / desktop spinner

GApplication is single-instance. A zombie `python3 main.py` holding the DBus name makes new launches spin forever.

```bash
ps -eo pid,cmd | grep '[m]ain.py'
kill <pid>   # or kill -9
# then
./run.sh
```

---

## Architecture (decided — do not reopen without user push)

| Layer | Choice |
|--------|--------|
| Shell | **GTK4 + libadwaita** (`window.py`) |
| Transcript | **WebKitGTK** local page under `web/` (**default**) |
| Fallback | Native GTK bubbles (`message_widgets.py`) if WebKit fails or env forced |
| Backend | **Python** — Ollama HTTP, streaming, SQLite, health |
| JS | **Presentation only** — Markdown, DOM, code cards, scroll, visual actions |

ZapZap was the *renderer clue* (browser for conversation), not “rewrite in PyQt.” Embed a **first-party** `web/` UI, not a remote app.

### Bridge (keep boring)

**Python → page:** `conversation_reset`, `empty_state`, `message_added`, `message_delta`, `message_done`, `message_error`, `message_removed`, `message_reset`, `theme_changed`, …

**Page → Python (intents only):** `ready`, `copy_text`, `open_link`, `regenerate`, `continue`, `edit_resend`, `delete_message`, …

No Ollama / no DB / no PMM inside JavaScript.

### Perf note

Do **not** dual-render native + WebKit for speed tests.

---

## Product north star

> Can a normal GNOME user install ChickenButt, discover a model, hold several conversations, close the app, return tomorrow, and continue **without knowing Ollama internals**?

When yes → legitimate standalone V1 product.

---

## What works today (solid)

### Chat & streaming
- Ollama chat streaming (batch ~33 ms) into WebKit deltas; stop generation.
- Model warm-up **load overlay** (“Loading model” / “Warming weights…”).
- Ephemeral greeting — **not** stored as chat history:
  - Title: `What's up, ChickenButt?`
  - Sub (two lines, spaced under title):
    - `Need a model?`
    - `Type in the box: ollama pull <model-name>`
- Last-used model persistence; startup prefers last successful model.

### Multi-chat history (SQLite)
- New / switch / delete conversations; auto-persist; restore last active on launch.
- Docked **sidebar** (Chats header + Recent + conversation list + **Model** section + Settings footer). Starts **closed** on every launch — sidebar-open state is intentionally not persisted; opening it during a session still works normally.
- Empty-chat lifecycle: prune empty drafts; avoid blank-chat spam.
- First user message can set the conversation title.
- Export current chat: **Markdown** / **JSON** (file chooser).

### Message actions
- Copy (plain text; chrome stripped), regenerate, continue, edit-resend user, delete.
- Code blocks: highlight, copy, expand/collapse.

### Ollama health
- Probe on refresh; **banner** for not running / not installed / no models / errors.
- Composer readable offline; **send blocked** until healthy + model ready.
- Retry / refresh wired to health actions.

### Composer commands (local — never sent to the LLM)
Type in the message box and Enter:

| Input | Implementation |
|--------|----------------|
| `ollama pull <model>` | **HTTP** `POST /api/pull` stream=true — NDJSON progress (no CLI, no ANSI) |
| `ollama list` | HTTP `/api/tags` → markdown table |
| `ollama ps` | HTTP `/api/ps` → markdown table |

- Progress updates replace the status bubble cleanly (`message_reset` while running, then `message_done`).
- Successful **pull** triggers **Refresh models**.
- Status bubbles are **not** added to `_messages` / API context.
- Do **not** shell out to `ollama` for pull (ANSI progress bars broke the UI).

### Composer UX
- Height: grow **1 → 8** visible lines (**6** if window height ≤ 560px); then internal scroll.
- Hard safety cap **64 000** characters; counter hidden until ~85% of cap.
- Floating pill on solid chat surface **`#121216`** (wallpaper **removed**).
- Keyboard hint above composer, centered; **fades** after chat has real messages.
- Send = paper-plane family icon + tooltip; Enter send / Shift+Enter newline / Esc → tray.

### Model control & header
- Model `Gtk.DropDown` lives in the **sidebar**, in its own Model section directly above the Settings footer — not under the header. It expands to the sidebar's inner width (no fixed pill width) at a fixed **38px** height.
- **Refresh** stays in the header, immediately left of burger (`Ctrl+R` / `win.refresh-models`); the health banner stays in the main chat column above the transcript — only the selector moved.
- App menu: New, Show Chat List, Settings, Export Chat Markdown/JSON…, Hide (Esc), Maximize (F11), Close (Ctrl+W), Quit (Ctrl+Q).

### Branding & tray
- Empty-state mark: tight `chickenbutt-light-icon.svg` / `dark-icon.svg` (not 1920×1080 logos).
- Dock/app icon: FreeDesktop icon-theme name `APP_ID`, installed publicly by `meson install` (see "Desktop integration" above); `scripts/generate-icons.py` only regenerates the tracked source assets, it does not install anything.
- **Tray / top-bar:** system **chat-bubble** symbolic + embedded IconPixmap (not the chicken).
- Close window → hide to tray.

### Explicitly removed / abandoned
- Chat wallpaper asset and CSS.
- Embedded VTE terminal drawer (reverted; broke launch / out of scope for now).
- Shelling out to `ollama pull` for progress UI.

---

## Repository map

| Path | Role |
|------|------|
| `main.py` | Adw.Application, tray, window icon, activate |
| `window.py` | **Main shell** (~3.8k LOC) — UI, stream lifecycle, multi-chat, composer commands |
| `transcript_view.py` | WebKit bridge (`WebTranscriptView`) |
| `web/app.js` / `app.css` / `index.html` | Transcript presentation |
| `conversation_store.py` | SQLite multi-conversation store |
| `ollama_client.py` | HTTP: tags, ps, generate (warm), **interruptible** chat stream, pull stream, list/ps formatters |
| `ollama_health.py` | Probe + classify errors |
| `tray.py` | StatusNotifier + DBus menu + IconPixmap |
| `message_widgets.py` | Native transcript fallback only |
| `x11_sidebar.py` | **Dead code.** Not imported by `main.py`, `window.py`, or anywhere else (`grep -rn x11_sidebar` outside this file and `meson.build`/`test_installed_layout.py` turns up nothing) — installed only because `meson.build` still lists it. Candidate for removal in a dedicated cleanup pass, not confirmed-in-use "support." |
| `release_info.py` | Single source of truth: `APP_ID`, `APP_NAME`, `VERSION` |
| `meson.build` | Installed runtime layout — see "Installed runtime layout" above |
| `data/*.desktop.in`, `data/*.metainfo.xml.in` | Canonical desktop-entry/AppStream templates — see "Desktop integration" above |
| `packaging/chickenbutt.in` | Launcher template, configured by Meson into `<prefix>/bin/chickenbutt` |
| `scripts/check_dependencies.py` | System-dependency checker — see "System dependencies" above |
| `DEPENDENCIES.md` | Canonical dependency list + Fedora/Ubuntu install commands |
| `profiling.py` | Untracked. Measurement-only, no-ops unless `CHICKENBUTT_PROFILE=1` |
| `scripts/` | generate-icons (source-asset generator only), smoke_gui, feature tests, `profile_*.py` benchmark drivers (untracked) |
| `icons/` | Brand SVGs, hicolor, tray PNGs |
| `STATUS_REPORT.md` | Stale mid-session snapshot — **HANDOFF.md (this file) is authoritative** |

**Vendor:** `web/vendor/` (marked, DOMPurify, highlight.js) — leave alone.

### Key constants (`window.py`)

```text
DEFAULT_WIDTH / HEIGHT          780 × 720
SIDEBAR_WIDTH                   220
COMPOSER_MIN_LINES              1
COMPOSER_MAX_LINES              8
COMPOSER_COMPACT_MAX_LINES      6
COMPOSER_COMPACT_WINDOW_HEIGHT  560
COMPOSER_CHAR_LIMIT             64000
COMPOSER_COUNTER_SHOW_RATIO     0.85
Chat / composer clamp           768px (~48rem WebKit column)
```

---

## Still open

### Maintenance debt surfaced by auditing this file (not fixed here — status notes only)

This file has a history of being patched incrementally by commits focused on their own topic, without reconciling older sections — several stale claims got fixed in the PR that introduced this note, but treat that as an improvement, not a guarantee of full accuracy. Verify any specific claim that matters against real code/tests/`git log` before relying on it. Known, verified problems not fixed in that pass:

- `x11_sidebar.py` is dead code — not imported by `main.py`, `window.py`, or anywhere else, but still installed because `meson.build` lists it (see Repository map above). Removing the file, its Meson entry, and updating `test_installed_layout.py`'s expected-file list is a small, bounded cleanup on its own.
- `conversation_store.py`'s module docstring still says "No multi-chat UI yet" — multi-chat has been implemented and tested (`scripts/test_multichat.py`) for a while now. Source-level stale comments like this exist outside HANDOFF.md too; this file can't catch all of them.

### Stability & performance

The correctness and performance defects that used to justify gating product work behind this section are fixed (see "Landed" and "Performance audit — closed out" above) — nothing below is a hard blocker to resuming product work.

1. Transcript virtualization or incremental history loading for very large (1000+ message) code-heavy histories — only if still needed; both restoration-cost fixes (scroll + wireCodeUi batching) are landed, so this is speculative until a real history is measurably slow.
2. Installation reproducibility — largely done: a real installed runtime via Meson, a desktop entry / public icon / AppStream metadata installed by Meson (see "Desktop integration" above), a system-dependency checker (`scripts/check_dependencies.py`), a canonical dependency doc (`DEPENDENCIES.md`, with verified Fedora/Ubuntu package names), and README documents the full source-install path. Still open: no screenshot/release-history metadata in the AppStream file, no tagged release, no Flatpak manifest, no CI (so `test_installed_layout.py` / `test_desktop_integration.py` / `test_dependency_declaration.py` aren't yet continuously exercised against a real meson/ninja install). `./run.sh` remains the source-tree dev launcher.
3. `STATUS_REPORT.md` vs this file — this file is authoritative; `STATUS_REPORT.md` is a stale mid-session snapshot. Consider deleting it rather than maintaining two.

### Product work (resume once the above is settled)

Ordered roughly by value:

1. **Chat rename + search** in sidebar  
2. **Per-chat generation settings** — system prompt, temperature, context, seed  
3. **Model metadata** in selector — size, loaded, context window, local vs `*:cloud` badge  
4. **Context-aware composer warning** (tokens vs model context; char counter only near 64k today)  
5. **Privacy UX** — open data folder is partly in Settings; delete-all, cloud warnings  
6. **Attachments v0** — drop text/source into context  
7. **Saved assistants / presets**  
8. **Richer Settings** shell  
9. **Response stats** (tokens/s, duration)  
10. Optional: move **Clear** from header into menu  

### Non-goals (for now)
- Model marketplace / HF browser  
- Embedded terminal / VTE (tried, reverted)  
- RAG library, MCP, voice, multi-endpoint admin  
- Platform feature parity with Open WebUI / LM Studio  

---

## Version 1.5+ (later)

- Attachments → then PDF/DOCX; full RAG later  
- Saved assistants  
- Vision paste, prompt history, snippets  
- Selective: STT/TTS, MCP, web search, image gen, side-by-side models  

---

## Coding conventions for agents

- Prefer **small, reviewable diffs**; do not invent parallel architecture docs unless asked.  
- **WebKit transcript is default** — do not reopen native-vs-WebKit without user push.  
- JS stays free of Ollama/DB.  
- Greeting is **ephemeral** — never persist `What's up, ChickenButt?` as history.  
- Empty conversations must not clutter Recent (respect prune rules).  
- **Pull via HTTP API only** — never dump raw CLI ANSI into the transcript.  
- Icon art: **tight square** SVGs; avoid huge padded artboards for UI marks.  
- After icon changes: `python3 scripts/generate-icons.py` to regenerate tracked source assets, then fully quit/restart for tray. The public app-grid/dock icon comes from `meson install` (see "Desktop integration" above), not from this script.
- Extend `scripts/smoke_gui.py` / feature tests when changing load/history/health/commands.  
- This **HANDOFF.md** is the authoritative status snapshot for handoff.
- **Commit discipline established this session, keep following it:** single-purpose commits. When a fix and an unrelated cleanup/test-stability change land in the same working-tree session, split them (see `406df07` pulled out of `62b207d`, or how `81f666c` was built from `git show HEAD:web/app.js` + just the fix lines to keep uncommitted profiling instrumentation out of it). Don't commit or push without being asked each time, even after doing so earlier in the same session.
- **Test scripts follow one pattern** (`scripts/test_generation_lifecycle.py`, `test_stream_cancellation.py`, `test_restore_scroll.py`, `smoke_gui.py`): a real `Adw.Application` + `ChatSidebar`, a `pump(seconds)` helper that iterates `GLib.main_context_default()`, and `wait_until(cond, timeout)` polling on top of it. Prefer driving the *actual* production code path (monkeypatch `OllamaClient.chat_stream` for fake generations, inject a JS spy via `evaluate_javascript` for DOM assertions) over mocking the function under test.
- Before profiling or testing restoration specifically, see the "gotcha" above about seeding a conversation that becomes active before `ChatSidebar.__init__` runs.

---

## Quick health check

```bash
cd ChickenButt
./run.sh
# Expect: Transcript: WebKit (default)
# UI: chicken empty mark, sidebar closed by default, header [↻][☰],
#     floating composer, greeting sub with ollama pull hint
python3 scripts/smoke_gui.py   # expect 25/25 PASS with Ollama available

# Full regression suite (all real WebKit, real GLib loop — no Ollama server
# required except smoke_gui.py):
python3 scripts/test_multichat.py
python3 scripts/test_ollama_health.py
python3 scripts/test_message_actions.py
python3 scripts/test_generation_lifecycle.py         # 14 checks — cross-chat corruption regressions
python3 scripts/test_stream_cancellation.py          # 21 checks — real stub-server socket cancellation
python3 scripts/test_restore_scroll.py               # 8 checks — restore scroll-call-count regression
python3 scripts/test_wire_code_ui_batch.py           # 8 checks — restore wireCodeUi batching regression
python3 scripts/test_markdown_sanitization.py        # 84 checks — DOMPurify sanitization boundary
python3 scripts/test_web_navigation_policy.py        # 56 checks — WebKit decide-policy confinement
python3 scripts/test_web_content_security_policy.py  # 53 checks — transcript CSP
python3 scripts/test_release_identity.py             # 8 checks — APP_ID/version consistency, old desktop-install path retired
python3 scripts/test_sidebar_interactions.py         # 37 checks — pointer cursor, model selector, sidebar state
python3 scripts/test_installed_layout.py             # 47 checks — real `meson install`; skips if meson isn't on PATH
python3 scripts/test_desktop_integration.py          # 37 checks — real `meson install`; desktop entry/icon/AppStream; skips if meson isn't on PATH
python3 scripts/test_dependency_declaration.py       # 50 checks — check_dependencies.py + doc content

./run.sh --version   # → "ChickenButt 0.1.0", no window
python3 scripts/check_dependencies.py                # → all required deps satisfied
```

WebKit import failure → log line and native fallback.
