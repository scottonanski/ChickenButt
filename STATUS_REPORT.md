# ChickenButt — Project Status Report

> **Superseded for handoff:** use **`HANDOFF.md`** (updated 2026-07-22) as the authoritative status. This file is a mid-session snapshot and may lag.

**Date:** 2026-07-21  
**Audience:** Next AI / engineer taking over  
**Product aim:** The nicest **lightweight GNOME client for local Ollama** — focus and feel over feature parity with Open WebUI / LM Studio.

**PMM (Persistent Mind Model):** out of band. Do not integrate unless the user explicitly asks.

---

## One-line summary

ChickenButt is a **GTK4 + libadwaita** tray-capable desktop chat app that talks to **Ollama over HTTP**, renders the conversation in an embedded **WebKit** page by default, and persists **multi-chat history in SQLite**. The UI was recently polished (composer, model bar, branding, tray icon). Core chat + history + message actions are largely in place; advanced model settings, attachments, and privacy chrome are still open.

---

## How to run

```bash
# Default — WebKit transcript
./run.sh

# Optional — native GTK bubble transcript
CHICKENBUTT_TRANSCRIPT=native ./run.sh

# Icons (dock / FreeDesktop name `chickenbutt`)
python3 scripts/install-icons.py

# Smoke / regression
python3 scripts/smoke_gui.py          # ~25 checks, expect all PASS
python3 scripts/test_multichat.py
python3 scripts/test_message_actions.py
python3 scripts/test_ollama_health.py
```

- **App ID:** `dev.local.ChickenButt` (must match desktop entry name).
- **Desktop entry:** `python3 scripts/install-desktop-entry.py` → installs under `~/.local/share/applications/`.
- **DB:** `~/.local/share/chickenbutt/conversations.db` (override with `CHICKENBUTT_DB`).
- **Settings JSON:** `~/.config/chickenbutt/settings.json` (e.g. last model, sidebar open).

---

## Architecture (decided — do not reopen without user push)

| Layer | Choice |
|--------|--------|
| Shell | GTK4 + libadwaita (`window.py`) |
| Transcript | **WebKitGTK** local page under `web/` (**default**) |
| Fallback | Native GTK bubbles (`message_widgets.py`) if WebKit fails or env forced |
| Backend | Python — Ollama HTTP, streaming, SQLite, health |
| JS | **Presentation only** — Markdown, DOM, code cards, scroll, visual actions |
| Bridge | Python posts JSON events; page posts intents (no Ollama/DB in JS) |

### Bridge events (representative)

**Python → page:** `conversation_reset`, `empty_state`, `message_added`, `message_delta`, `message_done`, `message_error`, `message_removed`, `message_reset`, `theme_changed`, …

**Page → Python:** `ready`, `copy_text`, `open_link`, `regenerate`, `continue`, `edit_resend`, `delete_message`, …  

Keep the bridge boring; extend carefully.

---

## Repository map

| Path | Role | ~size |
|------|------|--------|
| `main.py` | `Adw.Application`, tray wiring, window icon, activate | ~200 LOC |
| `window.py` | **Main shell** — header, sidebar, model picker, composer, health, streaming, multi-chat UI | ~3500 LOC |
| `transcript_view.py` | WebKit view + JSON bridge | ~150 LOC |
| `web/app.js` | Transcript presentation | ~1100 LOC |
| `web/app.css` | Transcript styles (`--bg: #121216`, chat column ~48rem) | ~480 LOC |
| `web/index.html` | Empty state + message root | short |
| `conversation_store.py` | SQLite multi-conversation store | ~530 LOC |
| `ollama_client.py` | List/load models, chat stream | ~160 LOC |
| `ollama_health.py` | Probe + classify not-running / no models / errors | ~220 LOC |
| `tray.py` | StatusNotifierItem + DBus menu + IconPixmap | ~510 LOC |
| `message_widgets.py` | Native transcript only | ~1000 LOC |
| `x11_sidebar.py` | X11 helpers for sidebar/window state (legacy/support) | — |
| `scripts/` | `install-icons.py`, `smoke_gui.py`, feature tests | — |
| `icons/` | Brand SVGs (light/dark logos & icons), hicolor, tray PNGs | — |
| `HANDOFF.md` | Older handoff (partially stale — prefer this report) | — |

**Vendor:** `web/vendor/` (marked, highlight.js) — leave alone.

---

## What works today (shipped / solid)

### Chat & streaming
- Ollama chat streaming with batching (~33 ms) into WebKit deltas.
- Stop generation.
- Model warm-up load overlay + ephemeral greeting (“What’s up, ChickenButt?”) **not** stored as a real message.
- Last-used model persistence; startup model pick prefers last successful model.

### Multi-chat history (SQLite)
- Create / switch / delete conversations.
- Auto-persist messages; restore last active chat on launch.
- Docked **sidebar** (“Chats”) with Recent list, New chat, Settings gear.
- Empty-chat lifecycle: prune empty drafts; avoid proliferating blank chats.
- First user message can title the conversation.
- Export current chat as **Markdown** or **JSON** (file chooser).

### Message actions (WebKit intents + native parity where relevant)
- Copy (with plain-text cleanup for chrome).
- Regenerate, continue, edit-and-resend user messages, delete.
- Code blocks: highlight, copy, expand/collapse (preview height vs full).

### Ollama health UX
- Probe on refresh; banner (not only modal) for not running / not installed / no models / errors.
- Composer can stay readable offline; **send blocked** until healthy + model ready.
- Retry / refresh paths wired to health actions.

### Composer (recent polish)
- Grow from **1 → 8** visible lines ( **6** if window height ≤ 560px); then **internal scroll**.
- Hard safety cap **64 000** characters (truncate on paste/insert).
- Char counter **hidden** until ~85% of hard cap (context-token warnings **not** implemented yet).
- Floating pill on solid chat surface (`#121216`); no wallpaper.
- Keyboard hint **above** composer, centered; **fades** once the chat has real messages.
- Send = paper-plane (`mail-send-symbolic` family) + tooltip “Send message (Enter)”.
- Enter send / Shift+Enter newline / Esc hide to tray.

### Model control (recent polish)
- Header: **Refresh** (`view-refresh-symbolic`) immediately left of **burger menu**.
- **Ctrl+R** → `win.refresh-models`; disabled while probe/load in flight.
- Model `Gtk.DropDown` alone under header: fixed pill width **`MODEL_DROPDOWN_WIDTH = 320`** (content-hug was too short; list follows control width).
- Modest corner radius (~10px), ~38px height — toolbar control, not a second composer.

### App menu
- New Conversation, Show Chat List, Settings, Export Chat Markdown/JSON (short labels).
- Hide (Esc), Maximize (F11), Close (Ctrl+W), Quit (Ctrl+Q) with accels shown in menu.

### Branding & chrome
- Empty/greeting mark: **tight** `chickenbutt-light-icon.svg` / `dark-icon.svg` (not 1920×1080 logos — those look like dots).
- Solid chat surface `#121216` (wallpaper **removed** from project).
- Window/dock icon: FreeDesktop `chickenbutt` via hicolor + `install-icons.py`.
- **Tray / top-bar indicator:** system **chat bubble** symbolic (e.g. `chat-bubble-text-symbolic`), **not** the chicken (chick stays for empty state + app icon). IconPixmap embedded so the panel does not scale a 16px SVG into a speck.

### Tray
- StatusNotifier + DBus menu: Show / Hide / Clear / Quit.
- Close window → hide to tray (`set_hide_on_close`).

---

## Tests

| Script | Intent |
|--------|--------|
| `scripts/smoke_gui.py` | ~25 GUI lifecycle checks (load, persist, restore, clear, health, switch) — expect **25/25 PASS** |
| `scripts/test_multichat.py` | Multi-conversation store behavior |
| `scripts/test_message_actions.py` | Greeting/ephemeral + action helpers |
| `scripts/test_ollama_health.py` | Health classification / UX expectations |

Prefer extending these over one-off manual-only changes when touching load/history/health.

---

## Known gaps / next product work

Ordered roughly by product value (aligns with original V1 list; several items **done** since early HANDOFF):

### Still open
1. **Chat search / rename UI** — store can update; full rename UX and search not first-class.
2. **Per-chat generation settings** — system prompt, temperature, context length, seed (Advanced panel).
3. **Model metadata in selector** — size, loaded/not, context window, local vs cloud badge.
4. **Context-aware composer warning** — char counter exists near 64k; **token estimate vs model context** not done.
5. **Privacy UX** — open data folder, delete all data, cloud-model warning for `*:cloud` tags.
6. **Attachments** — paste/drop text files into context first; vision later.
7. **Saved assistants / presets**.
8. **Settings shell** — button exists; prefs are minimal (“room for future”).
9. **Response stats** (tokens/s, duration) optional footer.
10. **Clear** still lives in header (user once floated moving it into the menu).

### Explicit non-goals (for now)
- Full model hub / Hugging Face browser  
- RAG library, MCP tools, voice, multi-endpoint admin  
- Dual-rendering WebKit + native for “speed tests”  
- Becoming Open WebUI / LM Studio  

---

## Recent UX decisions (this session — preserve unless user reverses)

1. **Composer height ≠ content length** — max 8 lines visible (6 compact), scroll inside; 64k hard cap.
2. **Composer floats** on solid chat bg; keyboard hint above, fades after chat starts.
3. **No wallpaper** — solid `#121216` only; asset deleted.
4. **Greeting icon** — tight brand SVG icons, theme-aware light/dark.
5. **Model row** — no outer pill, no flask; refresh in **header** left of burger; dropdown fixed **320px** pill (user asked to double content-sized pill, not clamp max alone).
6. **Tray icon** — chat bubble symbolic; chicken for brand surfaces.
7. **Menu copy** — “Export Chat Markdown/JSON…”; Hide/Maximize/Close show shortcuts.

User noted refresh-in-header may be **undone later** (“get ready to undo this”) — keep that move easy (already a `win.refresh-models` action + header pack).

---

## Key constants (`window.py`)

```text
DEFAULT_WIDTH / HEIGHT     780 × 720
SIDEBAR_WIDTH              220
MODEL_DROPDOWN_WIDTH       320   # closed pill + list target width
COMPOSER_MIN_LINES         1
COMPOSER_MAX_LINES         8
COMPOSER_COMPACT_MAX_LINES 6
COMPOSER_COMPACT_WINDOW_HEIGHT 560
COMPOSER_CHAR_LIMIT        64000
COMPOSER_COUNTER_SHOW_RATIO 0.85
Chat column / composer clamp 768px (WebKit --chat-column ~48rem)
```

---

## Coding conventions for agents

- Prefer **small, reviewable diffs** in `window.py` / `web/*` / store — not architecture rewrites.
- **WebKit transcript is default**; do not reopen native-vs-WebKit without user request.
- JS must stay free of Ollama/DB.
- Greeting text is **ephemeral** — never persist “What’s up, ChickenButt?” as history.
- Empty conversations should not clutter Recent (prune rules already exist — respect them).
- Icon art: use **tight square** SVGs (16×16 or 128×128 full-bleed). Avoid 1920×1080 “logo” pages for UI marks.
- After icon asset changes, run `python3 scripts/install-icons.py` and fully quit/restart for tray re-register.
- Update tests when changing load/history/health contracts.

---

## Suggested next sessions (if user does not specify)

**A. Product completeness**  
Per-chat system prompt + temp/context; rename chat in sidebar; cloud-model badge.

**B. Composer intelligence**  
Rough token estimate from selected model context (when Ollama exposes it); warn before send.

**C. Settings + privacy**  
Data path, delete-all, keep-alive, default model prefs.

**D. Attachments v0**  
Drop `.txt`/`.md`/source into composer as fenced context.

---

## Quick health check for the next agent

```bash
cd ChickenButt
./run.sh
# Console: Transcript: WebKit (default)
# UI: chicken empty mark, 320px model pill, header [↻][☰], floating composer
python3 scripts/smoke_gui.py   # expect 25/25 PASS with Ollama available
```

If WebKit import fails → log line and native fallback.

---

## Handoff note on stale docs

`HANDOFF.md` still describes an earlier snapshot (e.g. “no multi-chat”). **This file (`STATUS_REPORT.md`) is the accurate 2026-07-21 status.** Prefer it when ramping up; merge back into `HANDOFF.md` when convenient.
