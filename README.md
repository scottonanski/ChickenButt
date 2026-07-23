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

Linux with GTK4, libadwaita, WebKitGTK, PyGObject and dasbus (system packages, not pip), plus Python 3.10+. See **[DEPENDENCIES.md](DEPENDENCIES.md)** for the full list, why each one is required, and distro-specific install commands (Fedora, Ubuntu 24.04+). Check your system without installing anything:

```bash
python3 scripts/check_dependencies.py
```

[Ollama](https://ollama.com) is not a build/install dependency — ChickenButt starts and shows its own onboarding UI without it. See [Running Ollama](#running-ollama) below.

## Running (source tree, no install)

```bash
git clone https://github.com/scottonanski/ChickenButt.git
cd ChickenButt
./run.sh
```

Use the native GTK bubble transcript instead of the default WebKit view:

```bash
CHICKENBUTT_TRANSCRIPT=native ./run.sh
```

Running straight from the source tree does not add a launcher entry to
your app grid — use `./run.sh` from a terminal, or see **Install from
source** below for a real installed app-grid entry.

## Install from source

For a real `chickenbutt` command outside the checkout, ChickenButt uses [Meson](https://mesonbuild.com):

```bash
git clone https://github.com/scottonanski/ChickenButt.git
cd ChickenButt

python3 scripts/check_dependencies.py --build

meson setup build --prefix="$HOME/.local"
meson install -C build

"$HOME/.local/bin/chickenbutt" --version
"$HOME/.local/bin/chickenbutt"
```

- Make sure `$HOME/.local/bin` is on your `PATH` (add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile if `chickenbutt` isn't found afterward).
- This installs the `chickenbutt` command, its private runtime directory, a desktop launcher entry, and the public app icon — AppStream metadata is installed alongside them, and installed ChickenButt should appear in your GNOME app grid under "ChickenButt" (you may need to log out and back in, or restart the shell, for the icon/app-grid cache to pick it up). You can still launch it from a terminal by running `chickenbutt` at any time.
- Screenshot and release-history metadata in the AppStream file, plus Flatpak packaging, remain unfinished — see [HANDOFF.md](HANDOFF.md).
- Rebuilding after pulling changes:

  ```bash
  meson setup --reconfigure build --prefix="$HOME/.local"
  meson install -C build
  ```

- Uninstalling (from the retained build directory):

  ```bash
  ninja -C build uninstall
  ```

### Running Ollama

```bash
ollama serve   # if it isn't already running as a service
ollama list    # confirm at least one model is pulled
```

See the official [Ollama Linux documentation](https://docs.ollama.com/linux) for installation and running it as a service.

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
python3 scripts/test_generation_lifecycle.py
python3 scripts/test_stream_cancellation.py
python3 scripts/test_restore_scroll.py
python3 scripts/test_wire_code_ui_batch.py
python3 scripts/test_markdown_sanitization.py
python3 scripts/test_web_navigation_policy.py
python3 scripts/test_web_content_security_policy.py
python3 scripts/test_release_identity.py
python3 scripts/test_sidebar_interactions.py
python3 scripts/test_installed_layout.py       # real `meson install`; skips if meson isn't on PATH
python3 scripts/test_desktop_integration.py    # real `meson install`; skips if meson isn't on PATH
python3 scripts/test_dependency_declaration.py
```

## Project status

See [HANDOFF.md](HANDOFF.md) for the current architecture, what's implemented, and what's still open.

## License

[GPL-3.0-or-later](LICENSE).

Vendored third-party code: [mistune](vendor/mistune) (BSD-3-Clause), [marked.js](web/vendor/marked.min.js) (MIT), [DOMPurify](web/vendor/purify.min.js) (Apache-2.0 OR MPL-2.0), [highlight.js](web/vendor/highlight.min.js) (BSD-3-Clause).
