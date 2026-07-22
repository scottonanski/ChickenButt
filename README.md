<p align="center">
  <img src="icons/hicolor/256x256/apps/chickenbutt.png" width="128" height="128" alt="ChickenButt icon">
</p>

<h1 align="center">ChickenButt</h1>

A simple, lightweight GNOME desktop client for chatting with local [Ollama](https://ollama.com) models — focused on feel and ease of use rather than feature parity with Open WebUI or LM Studio.

## Features

- Native GTK4 + libadwaita shell with a tray icon
- Streaming chat over the Ollama HTTP API
- Multi-chat history, persisted locally in SQLite
- Markdown rendering with syntax-highlighted code blocks (copy, expand/collapse)
- Health checks with clear banners when Ollama isn't running or has no models
- Pull, list, and inspect models straight from the composer (`ollama pull <model>`, `ollama list`, `ollama ps`)
- Export any chat as Markdown or JSON

## Requirements

- Linux with GTK4 + libadwaita (GNOME or GNOME-compatible desktop)
- Python 3
- [Ollama](https://ollama.com) running locally
- Optional: `gir1.2-gtksource-5` for enhanced syntax highlighting (`sudo apt install gir1.2-gtksource-5`)

## Running

```bash
git clone https://github.com/scottonanski/ChickenButt.git
cd ChickenButt
./run.sh
```

Use the native GTK bubble transcript instead of the default WebKit view:

```bash
CHICKENBUTT_TRANSCRIPT=native ./run.sh
```

Install desktop icons (dock/app icon under the `chickenbutt` FreeDesktop name) and add ChickenButt to your app launcher:

```bash
python3 scripts/install-icons.py
python3 scripts/install-desktop-entry.py
```

## Data locations

| What | Where |
|------|-------|
| Conversation history | `~/.local/share/chickenbutt/conversations.db` (override with `CHICKENBUTT_DB`) |
| Settings | `~/.config/chickenbutt/settings.json` |

## Testing

```bash
python3 scripts/smoke_gui.py
python3 scripts/test_multichat.py
python3 scripts/test_message_actions.py
python3 scripts/test_ollama_health.py
```

## Project status

See [HANDOFF.md](HANDOFF.md) for the current architecture, what's implemented, and what's still open.

## License

[GPL-3.0-or-later](LICENSE).

Vendored third-party code: [mistune](vendor/mistune) (BSD-3-Clause), [marked.js](web/vendor/marked.min.js) (MIT), [highlight.js](web/vendor/highlight.min.js) (BSD-3-Clause).
