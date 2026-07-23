# ChickenButt — Repository Recovery

## 1. Mission and temporary status

This temporary document governs recovery because the repository currently
contains contradictory documentation, confirmed dead code and assets,
stale source claims, and no reliable single recovery ledger.

This document is temporary. It exists only to take the repository from its
current unreliable state to a clean, verified, maintainable baseline. It is
not a handoff mechanism, not an architecture reference, not a product
roadmap, not a session diary, and not a place to record stash or
working-tree state.

**Product development is paused.** No feature work, no product-facing
change, proceeds while this document is open, unless Scott explicitly
authorizes a specific exception in the Decision log (§7).

When every exit condition in §9 is met, this document is closed and
retired. A separate, permanent north-star document for product development
will be designed afterward, from scratch — this document must not quietly
turn into that document.

## 2. Ground-truth rules

These rules govern every claim made anywhere in this document, and every
recovery task done under it:

1. Current code and runtime behavior outrank documentation. If this
   document and the code disagree, the code is right until re-verified.
2. A test proving a file is installed does not prove the file is used.
3. Passing tests do not prove the tree is clean.
4. Commit messages and previous AI-written summaries (including in this
   document) are evidence leads to check, not truth to cite.
5. No cleanup task may be selected from stale documentation without
   checking current `main` first.
6. No local working-tree, stash, or session state may be recorded as
   repository truth anywhere in this document.
7. Every non-trivial assertion in this document must identify the evidence
   behind it (file, line range, command, or commit SHA) — not just assert.
8. This document records where evidence lives and what a task's status is.
   It is never itself proof that a claim remains true — later tasks must
   cite and recheck primary evidence in current `main`, not this document.
9. A citation in this document is a claim, not a guarantee — re-run the
   grep/read before relying on a line number for anything consequential.

## 3. Verified repository baseline

**Code baseline:** every finding in §4 was verified against the code tree at
`93375d4` — the last commit before recovery documentation work began. This
line only needs updating when a task actually changes code, tests, or
assets (RR-02 onward); it does not need to chase every documentation-only
commit to `main` (rule 8's direct-edit category), since those never touch
anything §4 cites. Current `origin/main` may be ahead of `93375d4` by any
number of doc-only commits at any given time — check `git log` if the exact
tip matters for something; this document does not track it as a moving
target.

**Runtime architecture, concisely:** `main.py` constructs one `Adw.Application`
(`ChickenButtApp`) which owns one `ChatSidebar` (`window.py`) and one
`TrayIcon` (`tray.py`). `ChatSidebar` is the composition root — it owns
`ConversationStore` (SQLite, `conversation_store.py`), `OllamaClient` (HTTP,
`ollama_client.py`), and the transcript, which is either a WebKit page
(`transcript_view.py`, default) or a native GTK fallback
(`message_widgets.py`, live — not dead — code path, active on WebKit-init
failure or `CHICKENBUTT_TRANSCRIPT=native`). The WebKit page and Python
communicate through a small bidirectional bridge: 9 Python→page event types,
6 page→Python intent types actually in use (a 7th, `open_link`, has a
Python-side handler but is never sent by the current JS — see §4). Settings
persist via `GLib.get_user_config_dir()/chickenbutt/settings.json`
(`window.py:52-53`) — XDG-aware, not a hardcoded path; typically resolves to
`~/.config/chickenbutt/settings.json` unless `XDG_CONFIG_HOME` is set.

**Confirmed product capabilities that must survive recovery unchanged:**
streaming chat with cancellation; multi-chat history (new/switch/delete/
export); Markdown rendering sanitized through vendored DOMPurify; WebKit
navigation confinement and a strict transcript CSP; tray icon via `dasbus`
(required, not optional); the Meson-installed runtime (private flat install
under `<prefix>/<libdir>/chickenbutt/`) plus desktop entry / public icon /
AppStream metainfo so an installed ChickenButt appears in the GNOME app
grid.

**Test situation:** the documented suite contains 15 `test_*.py` scripts
plus `smoke_gui.py`, 16 scripts total, all under `scripts/`, all manually
run. `smoke_gui.py` genuinely requires a reachable Ollama installation with
at least one pulled model to pass — it constructs a real `OllamaClient`,
waits for real model loading, and deliberately records failed checks
(`results.check(..., False)`, `smoke_gui.py:263,288`), not skipped ones,
when no models are available. No GitHub Actions workflow runs on `main`
(no `.github/` directory in the tree), and the documented suite is
manually invoked — this does not by itself rule out some other external
CI integration that wasn't checked. Meson-dependent tests
(`test_installed_layout.py`, `test_desktop_integration.py`) drive a real
`meson install` into a temp prefix and verify installed-file correctness —
but installed-file presence is not the same claim as runtime use (see §4).
Note on RR-02 through RR-08/RR-12's execution: at the time those tasks
were done, the environment had no `meson`/`ninja` on PATH and no
passwordless sudo to install them, so `test_installed_layout.py`
self-skipped (its own documented behavior,
`scripts/test_installed_layout.py:125-133`) rather than actually
exercising a real install for those changes; the other 13 scripts were
run directly and did pass. Scott then installed meson/ninja himself and
ran both meson-dependent tests directly against unmerged `main`, which
surfaced a real, previously-undiscovered bug (`find_pkglibdir()`'s
single-level-deep glob failing on Debian/Ubuntu's multiarch libdir
layout — see RR-13). Once meson/ninja became available in the execution
environment too and RR-13's fix was applied, both scripts were re-run for
real: `test_installed_layout.py` → 47 passed, 0 failed;
`test_desktop_integration.py` → 37 passed, 0 failed. All 15/15 scripts in
the documented suite now genuinely pass, not skipped — RR-04's and
RR-08's `meson.build`/installed-layout claims are confirmed by a real
install, not just static analysis.

**Deliberate, load-bearing constraints — do not "fix" these without
recognizing the cost:** the installed runtime is flat and un-namespaced by
design. Four separate modules (`main.py`, `transcript_view.py`,
`message_widgets.py`, `window.py`) each independently resolve "my own
directory, then a sibling folder" rather than sharing one path constant,
and `web/index.html` resolves `../icons/` the same way. A `src/`-style
package restructuring would require changing all of these in lockstep, plus
`meson.build`'s allowlist — this is not a free cleanup, and §5 does not
schedule it.

## 4. Confirmed recovery inventory

Rechecked against current code before inclusion here, not carried over from
any prior document without verification.

### Dead or unreachable code
- `x11_sidebar.py` — not imported by `main.py`, `window.py`, or any other
  runtime module (verified: `grep -rn "x11_sidebar"` across all `.py` files
  finds nothing outside `meson.build:66` and `test_installed_layout.py:64`).
  Still installed because `meson.build`'s allowlist includes it.
- `window.py`'s `open_link` intent handler (`elif typ == "open_link":`,
  around `window.py:2056`) — unreachable. `web/app.js` never sends a
  `postIntent` with `type: "open_link"` (verified: every literal
  `postIntent({ type: "..." })` call site grepped; only `ready`,
  `copy_text`, `regenerate`, `continue`, `delete_message`, `edit_resend`
  are actually sent). Appears superseded by WebKit-level navigation
  confinement (`transcript_view.py`'s `decide-policy` hook), which now
  handles external links directly instead of round-tripping through JS.
- `tray.py`'s file-based icon lookup branch (`_load_icon_pixmap`,
  `tray.py:98-113`, `if icon_theme_path:`) — unreachable given the only
  construction site. `main.py:59` always passes `icon_theme_path=""`
  (explicit, with the comment "Empty theme path → load from system
  Adwaita/Yaru icon theme"), and `main.py:93`'s `_resolve_tray_chat_icon`
  selects a system chat-bubble symbolic icon name, never touching
  `icons/tray/`'s chicken assets.
- `main.py:118` `_apply_window_icon`'s file-fallback loop (`for rel in
  ("icons/hicolor/128x128/apps/chickenbutt.png",
  "icons/chickenbutt-dash-desktop-icon.svg", "icons/tray/chickenbutt.png")`):
  the loaded `Gdk.Texture` is provably never applied — the only handling of
  it is `if texture is not None and hasattr(Gtk, "Window"): pass`, a no-op.
  The loop's only other effect is calling `window.set_icon_name(APP_ID)`
  again, redundant with the identical call already made before entering
  this method; the repository does not establish whether that call has an
  effect outside the local icon-theme lookup. Both `hicolor/128x128/apps/
  chickenbutt.png` and `chickenbutt-dash-desktop-icon.svg` exist on disk,
  so the current first valid asset is expected to succeed first — an
  exception while loading it would continue the loop rather than stopping
  it. **Needs a decision: repair this fallback to actually apply a
  texture, or remove it — currently it does neither.**

### Dead or unreachable assets
- `chickenbutt-logo.png` (repo root) — zero references in any `.py`/`.md`/
  `.build` file (verified via `grep -rl`). Not produced by any generator.
- `icons/chickenbutt-logo.png` — a second, distinct 256×256 PNG nested
  under `icons/`, found during RR-00 (`recovery-reports/
  00-initial-file-audit-discovery.md`). Zero references anywhere, same as
  the root file above but not previously recorded.
- `icons/hicolor/{16,22,24,32}x{16,22,24,32}/apps/chickenbutt-panel.png`
  — 4 files (verified: `find icons -iname "*panel*"`, exactly 4 paths, no
  5th size exists). Zero references anywhere. Not produced by the current
  `scripts/generate-icons.py` (its hicolor loop only emits
  `{size}x{size}/apps/chickenbutt.png`, `generate-icons.py:82`) — leftover
  from something else, not generator drift.
- `icons/tray/chickenbutt.png` and 9 further files in `icons/tray/`
  (`chickenbutt.svg`, `chickenbutt@2.png`, `chickenbutt-light.*`,
  `chickenbutt-dark.*`, `chickenbutt-symbolic.png`): **nine of the ten are
  unreachable from the current runtime** — their only prospective consumer,
  `tray.py`'s file-based pixmap lookup, requires a non-empty
  `icon_theme_path`, while `main.py:59` passes `icon_theme_path=""`.
  `icons/tray/chickenbutt.png` specifically is **referenced by a live but
  ineffective fallback path**: `main.py:118`'s `_apply_window_icon` loop
  can reach it if the two earlier candidates fail to load (both currently
  exist and are expected to succeed first) — but the resulting
  `Gdk.Texture` is never applied to anything (confirmed no-op, above). No
  file in `icons/tray/` currently has a demonstrated functional runtime
  consumer, but only nine of the ten are unreachable in the strict sense;
  the tenth is reachable-but-ineffective. **Unlike the panel.png files,
  all ten ARE actively (re)produced by `scripts/generate-icons.py:90-104`**
  — the generator is currently generating files nothing effectively
  consumes.

### Stale source comments and docstrings
- `conversation_store.py:4` — "No multi-chat UI yet." Multi-chat is fully
  implemented (§3).
- `x11_sidebar.py:314` — claims `run.sh` sets `GDK_BACKEND=x11`. `run.sh`'s
  full 6 lines contain no such thing. Wrong independent of the dead-code
  finding above — would still be wrong even if the file were wired in.
- `scripts/generate-icons.py`'s module docstring (confirmed) describes
  `icons/tray/` as a "StatusNotifier IconThemePath" and frames the
  light/dark chicken SVGs as the tray icons. Current runtime behavior
  contradicts this: `main.py:59` passes `icon_theme_path=""` to `TrayIcon`,
  and `main.py:93`'s `_resolve_tray_chat_icon` selects a system chat-bubble
  symbolic icon name (falling back to `"chat-message-new-symbolic"`) —
  never touching `icons/tray/`'s chicken assets at all. The generator's
  stated purpose for that directory no longer matches what the tray
  actually shows.
- Three dangling comment references to the now-deleted `HANDOFF.md`
  (verified via `grep -n "HANDOFF" meson.build scripts/*.py`):
  `meson.build:17`, `scripts/test_markdown_sanitization.py:276`,
  `scripts/test_sidebar_interactions.py:231`. Harmless (they don't assert
  behavior, just point at a file that's gone) but stale, and exactly the
  kind of thing RR-00's exhaustive pass exists to catch systematically
  rather than one at a time.

### Obsolete or contradictory documentation
- `HANDOFF.md` — retired under this recovery (§7 decision). Verified
  pattern behind that decision: a documentation commit recorded a "next
  task" that a later commit then completed without the label ever being
  removed; still later commits landed real security work with no
  corresponding doc update. Two subsequent correction passes on this file
  each fixed real problems and each still left the `open_link` claim above
  uncorrected.
- `STATUS_REPORT.md` — self-declared superseded on its own line 3
  ("Superseded for handoff: use HANDOFF.md...") while `HANDOFF.md` in turn
  claims `STATUS_REPORT.md` is the stale one — the two files contradict
  each other about which is authoritative. Retired under this recovery
  (§7 decision).
- `requirements-notes.txt` — compared against `DEPENDENCIES.md` line by
  line. Its GtkSource-package guidance is fully redundant
  (`DEPENDENCIES.md:47,102,119` already cover it for both distros). Its
  mistune-vendoring note ("mistune is vendored under vendor/mistune, no pip
  required") is **not** present anywhere in `DEPENDENCIES.md` and is
  independently confirmed true (`vendor/mistune/__init__.py` exists,
  `message_widgets.py:34-38` sets up the vendored `sys.path` and imports it
  bare). Recommendation: fold that one line into `DEPENDENCIES.md`, then
  delete this file (task RR-02, §6).

### Tests that verify presence, not use
- `scripts/test_installed_layout.py:64` — asserts `x11_sidebar.py` is
  present in the installed tree. Proves installation, not use. Will need
  updating in lockstep with any `x11_sidebar.py` removal (task RR-04, §6).

### Architectural concentration
- `ChatSidebar` (`window.py`, class body lines 495–3763, ~90 methods) —
  real concentration (UI construction, conversation management, message
  persistence, model health, and streaming all live in one class). Verified
  git-blame fact, stated once here because it matters for scope: the file
  was already 3,725 lines at the very first commit (`7a70930`); current
  `window.py` is 3,763 lines — net growth across every commit touching it
  since is +38 lines, pre-existing structure, not something introduced
  during this engagement. Independently re-derived coupling counts: the
  composer-sizing sub-cluster (`window.py:1239-1434`) touches shared
  conversation state once in ~200 lines; the streaming cluster
  (`window.py:2888-3763`) touches `self._web` 18 times in ~875 lines — the
  single most coupled region in the class.

### Missing automated enforcement
- No GitHub Actions workflow runs on `main`; the documented suite is
  manually invoked (§3). This document takes no position yet on whether CI
  is required before recovery can be considered complete — that's a
  decision point (§6, RR-09).

### Uncertain items requiring Scott's decision
- Whether to remove `x11_sidebar.py` outright or actually wire in
  edge-docking (currently: definitively dead, not "in progress").
- Whether to repair or remove `main.py`'s ineffective icon-fallback loop
  (above), and whether to keep generating the 10 unreachable/ineffective
  `icons/tray/` files for possible future use or stop and delete them.
- Whether `window.py` decomposition happens during this recovery at all, or
  is deferred to product-development work after this document retires.
- Whether manual test enforcement is acceptable long-term or CI is required
  before recovery is considered done.
- Whether the vendored `vendor/mistune/` files that ChickenButt's own call
  (`message_widgets.py:48`, `plugins=None`) never exercises — 11 plugin
  files, 8 directive files, 3 alternate renderer files, `toc.py` — should
  be trimmed to only what's used, or kept as-is on the reasoning that
  vendoring a whole library and using part of it is normal. Found during
  RR-00 (`recovery-reports/00-initial-file-audit-discovery.md`); not
  individually confirmed dead, since that would require tracing a
  third-party library's internals rather than ChickenButt's own code.

RR-00's classification itself is done — see
`recovery-reports/00-initial-file-audit-discovery.md` for the full,
file-by-file table. §4 above now reflects everything it found.

## 5. Recovery sequence

Bounded order, derived from the dependencies above — not from convenience:

1. **Bootstrap the recovery authority** — RR-01: create
   `REPOSITORY_RECOVERY.md`, retire `HANDOFF.md`/`STATUS_REPORT.md`, update
   `README.md`'s pointer, close PR #2 unmerged, delete the
   `docs/handoff-audit` branch. Must happen first — RR-00's classification
   results need somewhere non-contradictory to be recorded, and every
   later task needs the same.
2. **Complete tracked-file classification** — RR-00, now that the document
   to record it in exists. Covers all tracked files plus generator output,
   categorized per §6.
3. **Remaining documentation-source cleanup** — RR-02 (fold
   `requirements-notes.txt` into `DEPENDENCIES.md`, delete it), RR-03
   (reconcile the three stale source docstrings above).
4. **Dead-code removal** — RR-04 (`x11_sidebar.py`), RR-05 (`open_link`
   handler), RR-06 (icon-fallback loop), RR-12 (`tray.py`'s dead file-based
   icon lookup, added after RR-08 surfaced it). Independent of each other.
5. **Dead-asset and generator cleanup** — RR-07 (unambiguous orphans:
   `chickenbutt-logo.png`, 4 `chickenbutt-panel.png` files, no decision
   needed), RR-08 (the `icons/tray/` generator question — waits on Scott's
   decision).
6. **Test correction and enforcement** — `test_installed_layout.py` update
   as part of RR-04 once `x11_sidebar.py` is actually removed; RR-09 (CI
   decision) is separate and doesn't block anything else here.
7. **`ChatSidebar` responsibility reduction** — RR-10. Not started until
   Scott decides whether it happens during this recovery at all. If
   authorized, any extraction ordering proposed must be re-verified
   against current `main` at that time (Ground-truth rule 8/9), not
   adopted from any branch or document on faith.
8. **Final repository verification** — RR-11.

No step in this sequence assumes a `src/`, `tests/`, `assets/`, or `docs/`
restructuring, and none is proposed — nothing found in §4 requires one.

## 6. Active task ledger

| ID | Scope | Evidence | Status | Branch/PR | Verification required | Decision owner |
|----|-------|----------|--------|-----------|------------------------|-----------------|
| RR-01 | Delete `HANDOFF.md`, `STATUS_REPORT.md`; add `REPOSITORY_RECOVERY.md`; update `README.md`'s "Project status" pointer; close PR #2 unmerged; delete `docs/handoff-audit` branch (local+remote) | §4 "Obsolete or contradictory documentation"; §7 decision log | verified complete | PR #3 (`docs/repository-recovery-bootstrap`), merged as `e49c6d0` | `git status` clean (confirmed); no `HANDOFF.md`/`STATUS_REPORT.md` in tree (confirmed); `README.md` contains no dead link (confirmed); `origin/main` confirmed at `e49c6d0` immediately after the PR #3 merge (confirmed via `git ls-remote`, not a local-checkout claim); `docs/handoff-audit` and `docs/repository-recovery-bootstrap` both deleted locally and remotely (confirmed) | Scott (approved and merged) |
| RR-00 | Classify every tracked file and generator output against current `main` into: runtime, build/install, test/tooling, vendor, documentation, intentional asset, dead, or decision-pending | Full table: `recovery-reports/00-initial-file-audit-discovery.md`, all 112 tracked files | active — report written, awaiting Scott's review | `recovery/rr-00-file-audit` | full classification present, no gaps left unaccounted for; found one new orphaned asset (`icons/chickenbutt-logo.png`) and flagged vendored `mistune`'s unused-plugin surface as decision-pending, neither previously recorded in §4 | Scott (this PR) |
| RR-02 | Fold mistune-vendoring line into `DEPENDENCIES.md`; delete `requirements-notes.txt` | §4, line-by-line comparison above | verified complete | direct commit `0991fd3` (doc/text-only per §8, no PR) | grep confirmed zero remaining references to `requirements-notes.txt` before deletion; 13/15 test scripts run directly, 0 failures | Scott (recommendation pre-existed in this document; executed per Scott's 2026-07-23 instruction to proceed without further review, §7) |
| RR-03 | Reconcile stale source documentation: `conversation_store.py`'s module docstring; `x11_sidebar.py`'s `GDK_BACKEND` comment only if that file is retained (moot if removed by RR-04); `generate-icons.py`'s module docstring describing `icons/tray/` as the live tray IconThemePath, which current runtime behavior contradicts | §4 "Stale source comments and docstrings" | code complete, PR open, awaiting Scott's merge | PR #12 (`recovery/rr-03-stale-docstrings`); `generate-icons.py`'s docstring already corrected in PR #10 (RR-08) | direct read confirms corrected `conversation_store.py` text matches actual behavior (`create_conversation`/`list_conversations`/`delete_conversation`/`export_dict`/`export_markdown` all verified present); `x11_sidebar.py:314` moot, file removed in PR #7 (RR-04); 13/15 test scripts run directly, 0 failures | Scott (merge) |
| RR-04 | Remove `x11_sidebar.py`; remove its `meson.build` allowlist entry; update `test_installed_layout.py:64` | §4 "Dead or unreachable code" | verified complete | PR #7 (`recovery/rr-04-remove-x11-sidebar`), merged as `0d62ed5` | `test_installed_layout.py` updated to positively assert absence (moved to `FORBIDDEN_TOP_LEVEL`) rather than just dropping the requirement; 13/15 test scripts run directly, 0 failures; real `meson install` still pending — meson/ninja unavailable in the environment this was executed in, no passwordless sudo to install them | Scott decided "remove" was correct in principle (§4's own framing: "definitively dead, not in progress"); Claude executed under Scott's 2026-07-23 instruction to proceed without per-item confirmation (§7) — merge is the actual approval gate |
| RR-05 | Remove `window.py`'s unreachable `open_link` intent handler | §4 "Dead or unreachable code" | verified complete | PR #8 (`recovery/rr-05-remove-open-link-handler`), merged as `e154054` | zero remaining references to `open_link` in any runtime/source file (verified across the whole tracked tree excluding `recovery-reports/`, which necessarily still names the finding and this removal — historical record, not code); 13/15 test scripts run directly, 0 failures | Scott (merge) |
| RR-06 | Resolve `main.py`'s ineffective icon-fallback loop (repair or remove) | §4 "Dead or unreachable code" | verified complete | PR #9 (`recovery/rr-06-remove-icon-fallback-loop`), merged as `c3f1289` | confirmed the whole method was a no-op beyond the `set_icon_name(APP_ID)` call already made one line earlier; 13/15 test scripts run directly, 0 failures; manual on-screen icon verification still pending (needs a real GTK display) | Claude chose "remove" by default under Scott's 2026-07-23 instruction to proceed without per-item confirmation — repairing would mean inventing new behavior nobody requested, which is out of scope for a paused-feature-work recovery (§7); Scott's merge is the actual approval gate, and this default is easily reversed by not merging |
| RR-07 | Delete `chickenbutt-logo.png` and the 4 orphaned `chickenbutt-panel.png` files | §4 "Dead or unreachable assets" | verified complete | PR #6 (`recovery/rr-07-orphaned-assets`), merged as `96033ac` | grep re-confirmed zero references immediately before deletion (rule 9); 13/15 test scripts run directly, 0 failures | Scott (merge) |
| RR-08 | Resolve and implement the `icons/tray/` generator question (stop generating unreachable/ineffective files and delete them, or wire a real consumer in) | §4 "Uncertain items" | verified complete | PR #10 (`recovery/rr-08-tray-icons`), merged as `cfa149d` | confirmed all 10 files unreachable or reachable-but-ineffective given `icon_theme_path=""`; `generate-icons.py`'s tray-generation code and stale docstring removed; 13/15 test scripts run directly, 0 failures | Claude chose "stop generating + delete" by default under Scott's 2026-07-23 instruction to proceed without per-item confirmation — wiring a real consumer would be new feature work, out of scope while product development is paused (§7); Scott's merge is the actual approval gate |
| RR-09 | CI: adopt automated enforcement, or explicitly accept manual enforcement as permanent | §3 "Test situation" | blocked — decision not yet made | none yet | n/a until decided | Scott |
| RR-10 | `ChatSidebar` responsibility reduction (scope TBD pending authorization) | §4 "Architectural concentration" (coupling counts independently re-derived above) | blocked — not authorized | none yet | any adopted extraction plan must be re-verified against current `main` at authorization time | Scott |
| RR-11 | Final repository verification | all prior tasks | blocked — depends on RR-00 through RR-10 (and RR-12, RR-13) each reaching verified-complete, explicitly-retained, or explicitly-deferred status (§7) | none yet | full test run recorded, real build/install/run, `main` synced with `origin` | verification only |
| RR-12 | Remove `tray.py`'s dead file-based icon lookup branch inside `_load_icon_pixmap` (`if icon_theme_path:` block, ~lines 99-117) | §4 "Dead or unreachable code" listed this finding (`tray.py`'s `_load_icon_pixmap`, `tray.py:98-113`) but it was never assigned a ticket in this ledger — found and fixed while executing RR-08; added here now | code complete, PR open, awaiting Scott's merge | PR #11 (`recovery/rr-12-remove-tray-file-lookup`) | confirmed `main.py`'s only `TrayIcon` construction site passes `icon_theme_path=""`, so the branch never executes; `TrayIcon`'s public `icon_theme_path` constructor param, `self._icon_theme_path`, and the `IconThemePath` DBus property left untouched (StatusNotifierItem interface contract, not dead code); 13/15 test scripts run directly, 0 failures | Scott (merge) |
| RR-13 | Fix `find_pkglibdir()`: its glob only searched one directory level below any `lib*` root, so it never found the installed `chickenbutt/` dir on Debian/Ubuntu's multiarch libdir layout (e.g. `lib/x86_64-linux-gnu/chickenbutt`, two levels down). Fixed in both `scripts/test_installed_layout.py` **and** `scripts/test_desktop_integration.py`, which had a separately copy-pasted duplicate of the same function with the identical bug | Newly discovered — not previously in §4. Scott ran `test_installed_layout.py`/`test_desktop_integration.py` directly against unmerged `main` on his own machine (installing meson/ninja himself) and hit this; confirmed pre-existing and unrelated to RR-04/RR-08 — fails identically on unmodified `main` | verified complete | PR #13 (`recovery/rr-13-fix-pkglibdir-multiarch`), merged as `3034dc4` | meson/ninja became available in the execution environment partway through this task (Scott installed them); real verification then performed directly: `test_installed_layout.py` → 47 passed, 0 failed; `test_desktop_integration.py` → 37 passed, 0 failed; all 13 other test scripts re-run clean — all 15/15 scripts in the documented suite genuinely pass now, not skipped | Scott (merge) |

## 7. Decision log

| Date | Decision | Reason | Affected tasks |
|------|----------|--------|-----------------|
| 2026-07-23 | Reject a multi-document proposal (status + handoff + inventory + cleanup-guide). Adopt exactly one temporary document, `REPOSITORY_RECOVERY.md`, as sole authority during recovery. | Multiple competing internal documents was itself part of how the repository lost a trustworthy baseline. | Governs all RR tasks |
| 2026-07-23 | Retire and delete `HANDOFF.md`. Do not preserve it as a snapshot. | Repeated correction passes on it each fixed real problems and each missed more; the file cannot be trusted even after multiple audits. | RR-01 |
| 2026-07-23 | Retire and delete `STATUS_REPORT.md`. | Self-declared superseded, and contradicts `HANDOFF.md` about which file is authoritative. | RR-01 |
| 2026-07-23 | RR-01 and RR-00 execute as two separate PRs, in that order — not combined. RR-00 does not begin until RR-01 is reviewed and merged. | Keeps the bootstrap and the exhaustive audit independently reviewable; RR-00's results need a governing document already on `main` to be recorded in. | RR-00, RR-01 |
| 2026-07-23 | Scott instructed Claude to stop pausing for step-by-step review/approval on recovery tasks and proceed directly, using judgment on items this document had flagged as needing a decision. | Time constraint stated directly by Scott mid-session. | RR-02 through RR-08, RR-12 |
| 2026-07-23 | Under the above instruction, Claude executed RR-02, RR-03, RR-05, RR-07 as written (no real decision needed — recommendation already in this document or "no decision needed" per §5/§6), and made three default judgment calls on items §4/§6 had marked as needing Scott's decision: RR-04 removed `x11_sidebar.py` (this document's own §4 already characterized it as "definitively dead, not in progress"); RR-06 removed rather than repaired the icon-fallback loop (repairing means inventing new apply-texture behavior nobody requested — feature work, out of scope while product development is paused per §1); RR-08 stopped generating and deleted the 10 `icons/tray/` files rather than wiring a real consumer (same reasoning — wiring one in is new feature work). None of these three are irreversible: each is on its own open PR (#7, #9, #10) and Scott's merge is the actual approval gate, not this log entry. This entry records that Claude made the call, not that Scott separately reviewed each one — per Ground-truth rule 7, that distinction has to be explicit rather than implied. | RR-04, RR-06, RR-08 |
| 2026-07-23 | Added RR-12 to the ledger: `tray.py`'s dead file-based icon-lookup branch, a finding §4 already listed but which was never assigned a ticket in §6. Found and fixed while executing RR-08 (same tray-icon theme), scoped as its own PR since it's a different file/code path — not bundled into RR-08 per §8's "one bounded concern per change." | A real gap in this document's own tracking, not a new finding about the code — the dead-code evidence itself was already in §4. | RR-12 |
| 2026-07-23 | Added RR-13: fixed `find_pkglibdir()`'s single-level-deep glob, which silently skipped a large block of `test_installed_layout.py`'s own checks on any Debian/Ubuntu multiarch libdir install. Genuinely new — not in §4 before today. Scott discovered it by actually installing meson/ninja and running the meson-dependent tests directly against unmerged `main`, something the environment executing RR-02 through RR-12 could not do (no meson, no passwordless sudo to install it). | Confirms a real local run catches things sandbox verification alone cannot. | RR-13 |

Disposition of `requirements-notes.txt` was a recommendation in this
document; it is now resolved — see RR-02 above.

## 8. Rules for every recovery change

Two kinds of change happen while this document is open, and they are not
handled the same way.

**Any documentation or report change** — a typo fix, a stale citation
correction, a finding added to §4, a ledger status update, a brand-new
audit/classification report like RR-00's, an index like
`recovery-reports/README.md` — is a `.md` file with no code/test/asset
impact. All of it is edited directly on `main` and committed straight, no
branch, no PR, no matter how large or how much work went into it. **The
task number does not matter — RR-00 is not special.** If the change is a
markdown file, it never gets a PR. **A PR whose only content is
documentation is not allowed**, full stop.

**Everything else** — any change to actual `.py` code, tests, `meson.build`,
icons, or other real assets — goes through a branch, a PR, Scott's review,
and Scott's merge, same as always. That is where a mistake actually costs
something: broken imports, broken tests, deleted files that turn out to
matter.

For that second kind of change:

- Branch fresh from verified current `main` — check `git log`/`git status`
  first, not from what this document assumed at authoring time.
- One bounded concern per change. No unrelated cleanup riding along.
- Inspect the actual code before proposing or making any change — this
  document's citations are a starting point, not a substitute (rule 9, §2).
- Remove superseded implementation outright. Do not leave the old path
  next to the new one "just in case."
- Update or remove any test that protected the now-removed behavior in the
  same change — not as a follow-up.
- Run the relevant tests and record the actual command and actual result
  in this document's task ledger. Never state a test passed without having
  just run it in that change.
- Update this document's task ledger and, if relevant, §4's inventory as
  part of that PR's own commits, to record the PR's pre-merge status
  (code complete, tests run, ready for review) — never open a *second PR*
  later just to say the first one is done. That's two different edits at
  two different times, and they're not handled the same way:
  - The **pre-merge status** (what the change is, that tests were run and
    passed) is written as a commit on the PR's own branch, alongside the
    code change, so a reviewer sees the claim and the diff together.
  - The **post-merge confirmation** (status flips to "verified complete",
    the real merge commit SHA gets recorded) can only be written after the
    merge actually happens — that SHA doesn't exist before then, so it
    can never literally be "inside" the PR that produces it (see RR-01's
    own ledger row: `merged as e49c6d0` was necessarily added this way).
    This step is a markdown-only edit with no code/test/asset content, so
    it follows the direct-to-`main` rule above: committed straight to
    `main`, no branch, no PR. That is not "a separate follow-up PR" —
    it is not a PR at all, which is exactly what makes it allowed.
- No separate handoff, status, or inventory files are created. Ever, while
  this document is open.
- No unrelated refactoring rides along with a bounded task.

## 9. Recovery completion criteria

Recovery is complete only when all of the following are objectively true:

- RR-00's classification is complete and every tracked file/generator
  output has reached verified-complete, explicitly-retained, or
  explicitly-deferred status per a logged Scott decision in §7.
- `conversation_store.py:4`, `x11_sidebar.py:314`, and
  `generate-icons.py`'s stale claims are reconciled (fixed if the
  underlying file survives, moot if it's removed).
- `main.py`'s icon-fallback loop is either repaired or removed — not left
  in its current inert state.
- `scripts/generate-icons.py` produces only assets some runtime code path
  actually consumes, or Scott has explicitly decided to keep generating
  currently-unused ones for a stated future purpose.
- No test in the suite depends on the presence of a file that recovery
  removed.
- Either critical tests are wired into automated enforcement (CI), or
  Scott has explicitly accepted manual enforcement as the permanent state
  (§7).
- `ChatSidebar`'s responsibilities are reduced to a boundary Scott has
  agreed to, or Scott has explicitly deferred that work past recovery.
- A real `meson setup` / `meson install` / launch cycle succeeds against
  the recovered tree.
- Exactly one internal status document exists in the tree: this one, and
  only until closure.
- Local `main` is clean and synchronized with `origin/main`; no stray
  branches or PRs left open that this recovery created without
  disposition.

## 10. Replacement rule

Once every condition in §9 is met, this document is closed and retired —
not archived as ongoing reference, not left open "just in case." Only then
does work begin on a separate, permanent north-star document for normal
product development, designed fresh rather than evolved from this one.
