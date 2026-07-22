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

Each of the above is genuinely single-purpose — reviewed and split deliberately (e.g. `406df07` was pulled out of what became `62b207d` specifically so an unrelated test-stability fix wouldn't dilute the cancellation commit).

### Performance audit — instrumentation is uncommitted, on purpose

A measurement-only profiling pass (`CHICKENBUTT_PROFILE=1`, inert otherwise) was built to find the *next* bottleneck instead of guessing:

- **`profiling.py`** (new, tiny, untracked) — Python-side `mark(name)`, no-ops unless the env var is set.
- **`window.py` / `main.py` / `transcript_view.py`** — scattered `profiling.mark(...)` calls at lifecycle milestones (still uncommitted — these are `git status`-dirty right now, intentionally, pending a decision on whether/how to land them).
- **`web/app.js`** — a matching JS-side profiler (`mark`/`markRaf`, gated on a `?profile=1` URL flag) instrumenting `finalizeStream()` stages and the streaming/restore bridge. **Not currently in the working tree** — it was deliberately kept out of the `81f666c` commit (see below) and would need to be re-added from scratch if wanted again; it is not saved anywhere.
- **`scripts/profile_startup.py`**, **`scripts/profile_runtime.py`**, **`scripts/profile_ablation.py`** — benchmark drivers (untracked). Not part of the test suite; run manually.

**Why `web/app.js` doesn't currently have the JS profiler**: the `81f666c` commit needed to be *only* the scrolling fix. Since the profiler and the fix were both live edits to the same file, the clean way to isolate the commit was to rebuild `app.js` from `git show HEAD:web/app.js` (the true untouched baseline) plus just the two fix lines, then commit that — which means the JS profiler that existed moments before is gone from the working tree now, not merely uncommitted. If you want to re-run `profile_runtime.py`'s streaming/finalize/restore benchmarks, the JS-side `mark()`/`markRaf()` calls and the `?profile=1` handling in `web/app.js` need to be re-added first (they're straightforward — see the pattern already sitting in `window.py`'s `profiling.mark(...)` calls for what the JS side mirrored).

**Findings that still matter, even without re-adding the JS profiler:**
- WebKit's own page-load cost (~2.1–2.4s) dominates *startup*, is bimodal (first launch in a fresh cache vs. a warm one differ ~4×), and is not something ChickenButt's code controls.
- Ordinary prose streaming is fine; the existing ~33ms batching absorbs chunk count well regardless of how many chunks arrive.
- Syntax highlighting is the dominant *single-stage* cost wherever code is present (both live streaming DOM-update cost and `finalizeStream`'s stage breakdown).
- An ablation study (`scripts/profile_ablation.py`, temporary — reverted after use, not currently reflected in `app.js`) isolated that per-message `scrollIfPinned()` was the dominant restoration cost (now fixed in `81f666c`), and that batching `wireCodeUi()`'s per-message `requestAnimationFrame` code-height measurement is a *second, independent* win specifically for code-heavy histories (code-heavy 1000-msg restore: settled frame 4760ms baseline → 2949ms with scroll fix alone → **2485ms** with scroll fix + batched wireCodeUi). `highlightAllIn()` batching showed no meaningful effect and isn't worth doing.

### Next task (not started)

**Batch `wireCodeUi()` during restoration**, in its own commit, separate from everything above:
- Render each restored message normally (Markdown + highlight unchanged — do **not** touch `highlightAllIn`, measurements say it's not worth it).
- Don't call `wireCodeUi(body)` per message inside the restore loop.
- After the whole batch is appended, call `wireCodeUi(messagesEl)` once on the container — `wireCodeCopy`/`wireCodeExpand` already operate via `querySelectorAll`, so a single call over the whole container correctly wires every restored code block in one pass (this was verified in the ablation run: `dom_check` — row count, `.hljs` count, copy/expand button count, collapsed count — matched baseline exactly in every variant tested).
- Add a regression test analogous to `test_restore_scroll.py`: spy on however you choose to observe "wireCodeUi ran once, not N times" for a code-heavy 1000-message restore (the ablation's approach was a `?ablation=` URL flag + JS-side call counters — that machinery isn't in the tree anymore; a test-local spy in the same style as `test_restore_scroll.py`'s `scrollTop` interceptor is the cleaner path, since it doesn't require reintroducing any instrumentation into `app.js`).
- Re-profile and report baseline-vs-fixed before committing (same discipline as the scrolling fix).

**After that**, per the audit: the stalled-open HTTP defect is already fixed (`62b207d`), the scroll defect is fixed (`81f666c`), so the only items left from the performance audit are the wireCodeUi batch above and, longer-term, transcript virtualization / incremental history loading if code-heavy 1000+ message restores still aren't fast enough after both bounded fixes land (~2.5s was the last measured floor).

### A gotcha worth remembering for anyone writing more benchmarks/tests

If you seed a conversation into the DB and then construct a fresh `ChatSidebar`, that seeded conversation is the "active" one, so `ChatSidebar.__init__`'s own `_restore_history()` will restore it at construction time. If your test/benchmark *also* explicitly calls `switch_conversation()` on the same conversation afterward (common when forcing a fresh measurement), you get **two** restores of the same data back-to-back, silently doubling every count and cost you measure. Fix: after seeding the target conversation, create one more, empty conversation (`store.create_conversation(...)`) so *it* is active at construction time, and your explicit `switch_conversation()` call is the only real restore. This bit both `profile_ablation.py` and an early draft of the restore-scroll test.

---

## Run

```bash
# Default — WebKit transcript
./run.sh

# Optional fallback — native GTK bubble renderer
CHICKENBUTT_TRANSCRIPT=native ./run.sh

# Icons (FreeDesktop name chickenbutt, lowercase)
python3 scripts/install-icons.py

# Regression (see "Quick health check" below for the full current list)
python3 scripts/smoke_gui.py              # ~25 checks — expect all PASS
python3 scripts/test_multichat.py
python3 scripts/test_message_actions.py
python3 scripts/test_ollama_health.py
```

| Item | Value |
|------|--------|
| App ID | `dev.local.ChickenButt` (must match desktop entry) |
| Desktop entry | `python3 scripts/install-desktop-entry.py` → `~/.local/share/applications/` |
| SQLite DB | `~/.local/share/chickenbutt/conversations.db` (`CHICKENBUTT_DB` override) |
| Settings | `~/.config/chickenbutt/settings.json` (last model, sidebar open) |

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
- Docked **sidebar** (Chats + Recent + New + Settings footer).
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
- Model `Gtk.DropDown` only under header: fixed pill width **`MODEL_DROPDOWN_WIDTH = 320`**.
- **Refresh** in header, immediately left of burger (`Ctrl+R` / `win.refresh-models`).
- App menu: New, Show Chat List, Settings, Export Chat Markdown/JSON…, Hide (Esc), Maximize (F11), Close (Ctrl+W), Quit (Ctrl+Q).

### Branding & tray
- Empty-state mark: tight `chickenbutt-light-icon.svg` / `dark-icon.svg` (not 1920×1080 logos).
- Dock/app icon: FreeDesktop `chickenbutt` via `scripts/install-icons.py`.
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
| `x11_sidebar.py` | X11 helpers (support) |
| `profiling.py` | Untracked. Measurement-only, no-ops unless `CHICKENBUTT_PROFILE=1` |
| `scripts/` | install-icons, smoke_gui, feature tests, `profile_*.py` benchmark drivers (untracked) |
| `icons/` | Brand SVGs, hicolor, tray PNGs |
| `STATUS_REPORT.md` | Stale mid-session snapshot — **HANDOFF.md (this file) is authoritative** |

**Vendor:** `web/vendor/` (marked, highlight.js) — leave alone.

### Key constants (`window.py`)

```text
DEFAULT_WIDTH / HEIGHT          780 × 720
SIDEBAR_WIDTH                   220
MODEL_DROPDOWN_WIDTH            320
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

### Stability & performance (current priority — do this before resuming product features)

1. **Batch `wireCodeUi()` during restoration** — see "Next task" above. Bounded, already measured, ready to implement.
2. Longer-term, only if still needed after #1: transcript virtualization or incremental history loading for very large (1000+ message) code-heavy histories.
3. Markdown sanitization — `renderMarkdown()` pipes model output through `marked.parse()` straight into `innerHTML`, no sanitizer, no CSP. Flagged, not yet acted on. Matters more once cloud models / attachments / copied web content are in play.
4. Installation reproducibility — no `pyproject.toml`/`requirements.txt`, no distro-specific dependency list in the README. `./run.sh` just runs `python3 main.py`.
5. `STATUS_REPORT.md` vs this file — this file is authoritative; `STATUS_REPORT.md` is a stale mid-session snapshot. Consider deleting it rather than maintaining two.

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
- After icon changes: `python3 scripts/install-icons.py` and fully quit/restart for tray.  
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
# UI: chicken empty mark, 320px model pill, header [↻][☰], floating composer,
#     greeting sub with ollama pull hint
python3 scripts/smoke_gui.py   # expect 25/25 PASS with Ollama available

# Full regression suite added this session (all real WebKit, real GLib loop —
# no Ollama server required except smoke_gui.py):
python3 scripts/test_multichat.py
python3 scripts/test_ollama_health.py
python3 scripts/test_message_actions.py
python3 scripts/test_generation_lifecycle.py   # 14 checks — cross-chat corruption regressions
python3 scripts/test_stream_cancellation.py    # 21 checks — real stub-server socket cancellation
python3 scripts/test_restore_scroll.py         # 8 checks — restore scroll-call-count regression
```

WebKit import failure → log line and native fallback.
