# ChickenButt — handoff for next session

**Updated:** 2026-07-22  
**What it is:** GNOME desktop chat client for local **Ollama** (tray app, Adwaita chrome).  
**Product aim:** be **the nicest lightweight GNOME client for Ollama** — simple, fast, native-looking, immediately understandable — **not** a smaller clone of Open WebUI or LM Studio.

ChickenButt wins on **focus and feel**, not feature count.  
**PMM (Persistent Mind Model):** out of band — do **not** integrate unless the user explicitly asks.

---

## Run

```bash
# Default — WebKit transcript
./run.sh

# Optional fallback — native GTK bubble renderer
CHICKENBUTT_TRANSCRIPT=native ./run.sh

# Icons (FreeDesktop name chickenbutt, lowercase)
python3 scripts/install-icons.py

# Regression
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
| `window.py` | **Main shell** (~3.5k+ LOC) — UI, stream, multi-chat, composer commands |
| `transcript_view.py` | WebKit bridge |
| `web/app.js` / `app.css` / `index.html` | Transcript presentation |
| `conversation_store.py` | SQLite multi-conversation store |
| `ollama_client.py` | HTTP: tags, ps, generate (warm), chat stream, **pull stream**, list/ps formatters |
| `ollama_health.py` | Probe + classify errors |
| `tray.py` | StatusNotifier + DBus menu + IconPixmap |
| `message_widgets.py` | Native transcript fallback only |
| `x11_sidebar.py` | X11 helpers (support) |
| `scripts/` | install-icons, smoke_gui, feature tests |
| `icons/` | Brand SVGs, hicolor, tray PNGs |
| `STATUS_REPORT.md` | Mid-session snapshot (may lag this file) |

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

## Still open (next product work)

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

---

## Quick health check

```bash
cd ChickenButt
./run.sh
# Expect: Transcript: WebKit (default)
# UI: chicken empty mark, 320px model pill, header [↻][☰], floating composer,
#     greeting sub with ollama pull hint
python3 scripts/smoke_gui.py   # expect 25/25 PASS with Ollama available
```

WebKit import failure → log line and native fallback.
