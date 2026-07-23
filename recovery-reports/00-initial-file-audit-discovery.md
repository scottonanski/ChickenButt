# RR-00 — Initial File Audit / Discovery

This is the RR-00 deliverable described in `REPOSITORY_RECOVERY.md` §5/§6:
every tracked file (112 total, `git ls-files | wc -l`), classified against
current `main` at `93375d4` plus the doc-only commits that followed
(`e49c6d0` → `95f5a79`), which touched only `REPOSITORY_RECOVERY.md` and
are not re-verified per-file below since they didn't change any code this
report covers.

Categories: **runtime**, **build/install**, **test/tooling**, **vendor**,
**documentation**, **intentional asset**, **dead**, **decision-pending**.

This report does not remove or change anything. It only classifies.

---

## Runtime Python (imported transitively from `main.py`)

| File | Note |
|---|---|
| `main.py` | Entry point, `Adw.Application` |
| `window.py` | `ChatSidebar` — composition root |
| `conversation_store.py` | SQLite store |
| `ollama_client.py` | HTTP client |
| `ollama_health.py` | Health probe/classification |
| `release_info.py` | `APP_ID`/`APP_NAME`/`VERSION` |
| `tray.py` | StatusNotifier/DBus tray |
| `transcript_view.py` | WebKit bridge |
| `message_widgets.py` | Native transcript fallback (live, not dead — see `REPOSITORY_RECOVERY.md` §3) |
| `run.sh` | Dev launcher, `exec python3 main.py "$@"` |

## Dead code (already in `REPOSITORY_RECOVERY.md` §4 — restated for completeness, not re-argued)

| File | Note |
|---|---|
| `x11_sidebar.py` | Not imported anywhere; still installed via `meson.build`'s allowlist. Decision-pending (RR-04). |

## Build / install only

| File | Note |
|---|---|
| `meson.build` | Build config |
| `packaging/chickenbutt.in` | Launcher template |
| `data/io.github.scottonanski.ChickenButt.desktop.in` | Desktop entry template |
| `data/io.github.scottonanski.ChickenButt.metainfo.xml.in` | AppStream template |
| `.gitignore` | Git config, not shipped |

## Test / tooling

| File | Note |
|---|---|
| `scripts/smoke_gui.py` | GUI smoke test, requires live Ollama + model |
| `scripts/test_dependency_declaration.py` | Tests `check_dependencies.py` + doc content |
| `scripts/test_desktop_integration.py` | Real `meson install`, desktop entry/icon/AppStream |
| `scripts/test_generation_lifecycle.py` | Cross-chat stream corruption regression |
| `scripts/test_installed_layout.py` | Real `meson install`, layout/exclusion checks |
| `scripts/test_markdown_sanitization.py` | DOMPurify sanitization boundary |
| `scripts/test_message_actions.py` | Message action persistence |
| `scripts/test_multichat.py` | New/switch/restore across conversations |
| `scripts/test_ollama_health.py` | Health classification/probe |
| `scripts/test_release_identity.py` | `APP_ID`/version consistency |
| `scripts/test_restore_scroll.py` | Restore scroll-call-count regression |
| `scripts/test_sidebar_interactions.py` | Sidebar/model-selector interactions |
| `scripts/test_stream_cancellation.py` | Real stub-socket cancellation |
| `scripts/test_web_content_security_policy.py` | Transcript CSP |
| `scripts/test_web_navigation_policy.py` | WebKit decide-policy confinement |
| `scripts/test_wire_code_ui_batch.py` | Restore wireCodeUi batching regression |
| `scripts/check_dependencies.py` | Dependency checker (not a test; dev/build tool) |
| `scripts/generate-icons.py` | Source-asset generator (dev tool). Currently regenerates 10 `icons/tray/` files nothing effectively consumes — already flagged, RR-08. |

All 15 `test_*.py` files plus `smoke_gui.py` are what `REPOSITORY_RECOVERY.md`
§3 already counts as "16 scripts total" — confirmed still accurate at 16
(`ls scripts/test_*.py | wc -l` → 15, plus `smoke_gui.py`).

## Web runtime (transcript page)

| File | Note |
|---|---|
| `web/index.html` | Loads all 5 vendor files below by literal `<script>`/`<link>` tag, plus `app.css`/`app.js` |
| `web/app.js` | Presentation logic, Python↔page bridge |
| `web/app.css` | Transcript styling |

## Vendor — JS/CSS (all confirmed referenced by literal tag in `web/index.html`)

| File | Note |
|---|---|
| `web/vendor/marked.min.js` | Markdown parse |
| `web/vendor/purify.min.js` | DOMPurify sanitization |
| `web/vendor/highlight.min.js` | Syntax highlighting |
| `web/vendor/highlight-github.min.css` | Light theme |
| `web/vendor/highlight-github-dark.min.css` | Dark theme |

## Vendor — Python (`vendor/mistune/`, native-fallback markdown only)

`message_widgets.py:48` calls `mistune.create_markdown(renderer="ast")` —
**no `plugins=` argument**, so `plugins=None` (confirmed:
`vendor/mistune/__init__.py`'s `create_markdown` signature defaults
`plugins` to `None`, and `import_plugin()` is only ever invoked per
requested plugin name — never triggered here).

| File(s) | Note |
|---|---|
| `__init__.py`, `block_parser.py`, `core.py`, `inline_parser.py`, `list_parser.py`, `markdown.py`, `helpers.py`, `util.py`, `py.typed`, `renderers/__init__.py`, `renderers/html.py`, `plugins/__init__.py` | **Vendor, imported.** `__init__.py`'s own top-level imports (`vendor/mistune/__init__.py:12-17`) unconditionally pull in `HTMLRenderer` and the `plugins` module machinery even though ChickenButt's call never instantiates/activates them — these files load when `import mistune` runs, whether or not their classes end up used. |
| `plugins/{abbr,def_list,footnotes,formatting,math,ruby,speedup,spoiler,table,task_lists,url}.py` (11 files), `directives/{__init__,_base,_fenced,_rst,admonition,image,include,toc}.py` (8 files), `renderers/{markdown,rst,_list}.py` (3 files), `toc.py` (1 file) | **Decision-pending, not individually confirmed dead.** None of these are reachable through `import_plugin()` given `plugins=None`, and neither the `"ast"` nor `"html"` renderer path needs the `markdown`/`rst`/`_list` renderer variants (confirmed: no `renderers/ast.py` exists — `"ast"` is handled inline in `vendor/mistune/__init__.py:45,70`, not via a separate renderer class). I did not trace every one of these 23 files individually to rule out some indirect import path inside the vendored library itself — that's a third-party library's internal structure, not ChickenButt's own code, and fully tracing it is disproportionate to this report's scope. **Flagging as a decision point**: either accept this as normal "we vendor the whole library, only use part of it" (common and reasonable), or trim the vendor copy to only the exercised surface. Not classified as "dead" outright since that requires more certainty than a scope-bounded pass can honestly claim. |

## Icons — intentional assets (standard FreeDesktop hicolor icon theme; consumed via icon-name lookup, not always a literal path grep hit)

| File(s) | Note |
|---|---|
| `icons/hicolor/{16,22,24,32,48,64,128,256}x{same}/apps/chickenbutt.png`, `icons/hicolor/scalable/apps/chickenbutt.svg` | Standard hicolor theme sizes, installed via `meson.build`'s `install_subdir('icons', ...)`. `128x128` is also the literal first fallback path in `main.py:135`. `256x256` is also hardcoded in `README.md`'s `<img>` tag. The rest are consumed indirectly through GTK icon-theme resolution (`theme.has_icon(APP_ID)`), not a literal path reference each — that's normal for an icon theme, not evidence of being unused. |
| `icons/hicolor/index.theme` | Standard hicolor theme metadata file. `scripts/generate-icons.py:106-109` checks for its existence but doesn't regenerate its content — not itself referenced by Python runtime code, but required by the FreeDesktop icon theme spec for `icons/hicolor/` to function as a theme at all. |
| `icons/chickenbutt-dash-desktop-icon.svg` | Public installed app icon source (`meson.build`'s desktop-integration install), also `main.py`'s second icon-fallback path, also `generate-icons.py`'s hicolor source |
| `icons/chickenbutt-light-icon.svg`, `icons/chickenbutt-dark-icon.svg` | Empty-state branding (`window.py`), also tray-icon SVG sources in `generate-icons.py` |

## Icons — dead/orphaned (already in §4, restated)

| File(s) | Note |
|---|---|
| `chickenbutt-logo.png` (repo root) | Zero references anywhere (confirmed again this pass) |
| `icons/hicolor/{16,22,24,32}x{same}/apps/chickenbutt-panel.png` (4 files) | Zero references, not produced by current generator |
| `icons/tray/*` (10 files) | 9 unreachable + 1 reachable-but-ineffective (§4) — actively regenerated by `generate-icons.py` despite being unconsumed |

## Icons — dead, newly found this pass

| File | Note |
|---|---|
| `icons/chickenbutt-logo.png` | **Not previously recorded.** A second, distinct 256×256 PNG (9,644 bytes) nested under `icons/`, separate from the root `chickenbutt-logo.png`. `grep -rn "icons/chickenbutt-logo\|chickenbutt-logo.png"` across `.py`/`.md`/`.build`/`.js`/`.html` finds only this report and `REPOSITORY_RECOVERY.md`'s existing entries about the *root* file — nothing references this nested one. Zero consumers found. |

## Documentation

| File | Note |
|---|---|
| `README.md` | External-facing, live, accurate per prior verification passes |
| `DEPENDENCIES.md` | Canonical dependency list, live |
| `REPOSITORY_RECOVERY.md` | This recovery's own authority document |
| `LICENSE` | GPL-3.0-or-later |
| `requirements-notes.txt` | **Obsolete, already flagged for RR-02** — its one unique fact (mistune is vendored, no pip) is not yet folded into `DEPENDENCIES.md`; still exists, still redundant on the GtkSource guidance |

---

## Summary

- 112 tracked files total.
- 1 confirmed-dead code file (`x11_sidebar.py`), already known.
- 6 confirmed-dead/orphaned assets, 5 already known + **1 newly found this pass** (`icons/chickenbutt-logo.png`).
- 10 `icons/tray/` files: unreachable/ineffective, already known, still actively regenerated by `generate-icons.py`.
- 23 vendored `mistune` files: not individually confirmed dead, flagged as a decision point rather than asserted — see above for why that line was drawn where it was.
- Everything else classifies cleanly as runtime, build/install, test/tooling, vendor (confirmed used), intentional asset, or live documentation.
- No new dead *code* paths found beyond what §4 already had — the new findings this pass are one orphaned asset and the vendored-mistune scope question.

## Additions folded into `REPOSITORY_RECOVERY.md` §4 in this same PR

Per §8's rule (ledger/§4 updates happen in the same PR as the change that
makes them true — this report is that change):

1. `icons/chickenbutt-logo.png` — added to "Dead or unreachable assets."
2. The vendored-mistune scope question — added to "Uncertain items
   requiring Scott's decision."
