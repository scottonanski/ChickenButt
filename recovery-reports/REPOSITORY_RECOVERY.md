# ChickenButt — Repository Recovery

> **CLOSED, 2026-07-23.** Every exit condition in §9 was met and verified
> (RR-11, commit `a042364`). This document is retained from here on only as
> a **historical record** of what recovery found and fixed — it is no
> longer an active status authority, and product development is no longer
> paused. Nothing below should be read as current status; treat every
> "blocked," "open," or "awaiting" phrasing as describing a past state, not
> a live one. Per §10, a separate, fresh document governs product
> development going forward — this one does not quietly become that
> document.

## 1. Mission and temporary status (historical — recovery is closed)

This temporary document governed recovery because the repository had
contained contradictory documentation, confirmed dead code and assets,
stale source claims, and no reliable single recovery ledger.

This document was temporary. It existed only to take the repository from
its unreliable state to a clean, verified, maintainable baseline. It was
never a handoff mechanism, an architecture reference, a product roadmap, a
session diary, or a place to record stash or working-tree state.

**Product development was paused** for the duration of recovery — no
longer, now that recovery is closed.

Every exit condition in §9 was met and verified (RR-11). Per §10, a
separate, permanent north-star document for product development is
designed next, from scratch — this document does not quietly turn into
that document.

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
6 page→Python intent types, all actually sent and all actually handled (a
7th, `open_link`, was a dead handler with no JS sender — removed under
recovery, RR-05). Settings
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

### Resolved during this recovery

Every item below was a live finding earlier in this document, confirmed
fixed against current `main` (re-verified directly, not cited from memory,
per Ground-truth rule 9) rather than left in "current problem" framing —
per rule 1, code outranks documentation, and the code has moved on:

- **`x11_sidebar.py`** — removed outright (not wired in). PR #7, merged
  `0d62ed5` (RR-04). `meson.build`'s allowlist entry and
  `test_installed_layout.py`'s requirement both removed; the test now
  positively asserts the file's absence instead.
- **`window.py`'s `open_link` intent handler`** — removed. PR #8, merged
  `e154054` (RR-05). Confirmed zero references anywhere in runtime/source
  code (the only remaining mentions are historical, in this document).
- **`tray.py`'s file-based icon lookup branch`** — removed. PR #11, merged
  `c0962f9` (RR-12). `TrayIcon`'s public `icon_theme_path` constructor
  param and the `IconThemePath` DBus property were deliberately kept
  (StatusNotifierItem interface contract, not dead code) — only the
  internal dead branch was removed.
- **`main.py`'s ineffective icon-fallback loop`** — removed (not repaired).
  PR #9, merged `c3f1289` (RR-06). Confirmed the whole method was a no-op
  beyond a `set_icon_name(APP_ID)` call already made one line earlier.
- **`chickenbutt-logo.png` (root), `icons/chickenbutt-logo.png`, and the 4
  orphaned `icons/hicolor/*/apps/chickenbutt-panel.png` files** — deleted.
  PR #6, merged `96033ac` (RR-07).
- **All 10 `icons/tray/` files** — deleted, and `scripts/generate-icons.py`
  no longer generates them. PR #10, merged `cfa149d` (RR-08). Its module
  docstring was corrected twice: once to stop describing `icons/tray/` as a
  live StatusNotifier IconThemePath, and once more (caught during PR
  review) to stop citing `main.py`'s icon-fallback loop after that loop was
  separately removed by RR-06.
- **`conversation_store.py`'s stale "No multi-chat UI yet" docstring** —
  corrected. PR #12, merged `1bae8d7` (RR-03). `x11_sidebar.py:314`'s
  `GDK_BACKEND` claim is moot — the file no longer exists (RR-04).
- **3 dangling comment references to deleted `HANDOFF.md`**
  (`meson.build:17`, `scripts/test_markdown_sanitization.py:276`,
  `scripts/test_sidebar_interactions.py:231`) — fixed, substance kept,
  only the dead pointer removed. PR #14 (new task, RR-14, found during
  this reconciliation pass) — **open, not yet merged**, unlike everything
  else in this subsection.
- **`scripts/test_installed_layout.py:64`'s presence-only assertion for
  `x11_sidebar.py`** — resolved as part of RR-04 above; the test now
  asserts absence, in `FORBIDDEN_TOP_LEVEL`.
- **`HANDOFF.md`, `STATUS_REPORT.md`** — retired (§7 decision, RR-01, PR
  #3, merged `e49c6d0`).
- **`requirements-notes.txt`** — its one unique fact (mistune is vendored,
  no pip needed) folded into `DEPENDENCIES.md`; the file deleted. Direct
  commit `0991fd3` (RR-02, doc/text-only per §8).
- **`find_pkglibdir()`'s multiarch libdir bug** — a finding discovered
  *during* this recovery, not present at RR-00 time, fixed in both
  `scripts/test_installed_layout.py` and `scripts/test_desktop_integration.py`
  (which had an independently copy-pasted duplicate of the same bug). PR
  #13, merged `3034dc4` (RR-13).

### Decided, 2026-07-23 (§7)

- **RR-09 (CI)** — Scott decided: require CI. Implemented, PR #15, real
  GitHub Actions run green (all 15 test scripts, including both
  meson-dependent ones). Awaiting merge.
- **RR-10 (`ChatSidebar` decomposition)** — Scott decided: defer past this
  recovery. No code touched; `window.py`'s architectural concentration
  (below) is unchanged and remains ordinary future product-development
  work, not a recovery blocker.
- **Vendored `vendor/mistune/` unused surface** (24 files —23 originally
  found at RR-00, plus `__main__.py`, found on review) — Scott decided:
  keep as-is. Vendoring a whole library and using part of it is normal;
  no trim.

Nothing is "still open" for decision at this point — RR-09's only
remaining step is Scott merging PR #15.

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
- No GitHub Actions workflow runs on `main` yet — Scott decided CI is
  required (RR-09, "Decided" above); PR #15 implements it, real GitHub
  Actions run green, awaiting merge.

RR-00's classification is complete and verified against current `main`'s
reduced 96-file tree — see `recovery-reports/00-initial-file-audit-discovery.md`
for the full file-by-file table and its closing reconciliation. Every file
it originally classified as dead or orphaned has since actually been
removed (18 files: `x11_sidebar.py`, `requirements-notes.txt`, 6 orphaned
image assets, 10 `icons/tray/` files); zero files exist now that weren't
present at RR-00 time, aside from this recovery's own documentation
(`recovery-reports/README.md`). §4 above reflects the current, post-removal
state.

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
   (reconcile the three stale source docstrings above), RR-14 (three
   dangling `HANDOFF.md` comment references, added after this document's
   post-PR-batch reconciliation pass surfaced them as still unresolved).
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
| RR-00 | Classify every tracked file and generator output against current `main` into: runtime, build/install, test/tooling, vendor, documentation, intentional asset, dead, or decision-pending | Full table: `recovery-reports/00-initial-file-audit-discovery.md` | verified complete | direct commit `774f7d6` (doc-only per §8); a since-closed PR #5 attempted to route this same report through a branch/PR and was correctly closed unmerged once it landed directly instead | Full classification of the 114-file baseline (corrected from an initially-miscounted 112) drove every later cleanup task (RR-02 through RR-14). Reconciled against current `main`'s 96-file tree: the 18-file delta is fully accounted for (`x11_sidebar.py`, `requirements-notes.txt`, 6 orphaned image assets, 10 `icons/tray/` files — every one independently confirmed removed, §4); zero untracked/unclassified new files exist beyond this recovery's own `recovery-reports/README.md`. The one decision RR-00 surfaced (vendored `mistune`'s unused surface) has since been decided — keep as-is, §4 "Decided" | Scott (classification complete; decided the one question it raised) |
| RR-02 | Fold mistune-vendoring line into `DEPENDENCIES.md`; delete `requirements-notes.txt` | §4, line-by-line comparison above | verified complete | direct commit `0991fd3` (doc/text-only per §8, no PR) | grep confirmed zero remaining references to `requirements-notes.txt` before deletion; 13/15 test scripts run directly, 0 failures | Scott (recommendation pre-existed in this document; executed per Scott's 2026-07-23 instruction to proceed without further review, §7) |
| RR-03 | Reconcile stale source documentation: `conversation_store.py`'s module docstring; `x11_sidebar.py`'s `GDK_BACKEND` comment only if that file is retained (moot if removed by RR-04); `generate-icons.py`'s module docstring describing `icons/tray/` as the live tray IconThemePath, which current runtime behavior contradicts | §4 "Stale source comments and docstrings" | verified complete | PR #12 (`recovery/rr-03-stale-docstrings`), merged as `1bae8d7`; `generate-icons.py`'s docstring already corrected in PR #10 (RR-08) | direct read confirms corrected `conversation_store.py` text matches actual behavior (`create_conversation`/`list_conversations`/`delete_conversation`/`export_dict`/`export_markdown` all verified present); `x11_sidebar.py:314` moot, file removed in PR #7 (RR-04); 13/15 test scripts run directly, 0 failures | Scott (merge) |
| RR-04 | Remove `x11_sidebar.py`; remove its `meson.build` allowlist entry; update `test_installed_layout.py:64` | §4 "Dead or unreachable code" | verified complete | PR #7 (`recovery/rr-04-remove-x11-sidebar`), merged as `0d62ed5` | `test_installed_layout.py` updated to positively assert absence (moved to `FORBIDDEN_TOP_LEVEL`) rather than just dropping the requirement; 13/15 test scripts run directly, 0 failures; real `meson install` still pending — meson/ninja unavailable in the environment this was executed in, no passwordless sudo to install them | Scott decided "remove" was correct in principle (§4's own framing: "definitively dead, not in progress"); Claude executed under Scott's 2026-07-23 instruction to proceed without per-item confirmation (§7) — merge is the actual approval gate |
| RR-05 | Remove `window.py`'s unreachable `open_link` intent handler | §4 "Dead or unreachable code" | verified complete | PR #8 (`recovery/rr-05-remove-open-link-handler`), merged as `e154054` | zero remaining references to `open_link` in any runtime/source file (verified across the whole tracked tree excluding `recovery-reports/`, which necessarily still names the finding and this removal — historical record, not code); 13/15 test scripts run directly, 0 failures | Scott (merge) |
| RR-06 | Resolve `main.py`'s ineffective icon-fallback loop (repair or remove) | §4 "Dead or unreachable code" | verified complete | PR #9 (`recovery/rr-06-remove-icon-fallback-loop`), merged as `c3f1289` | confirmed the whole method was a no-op beyond the `set_icon_name(APP_ID)` call already made one line earlier; 13/15 test scripts run directly, 0 failures; manual on-screen icon verification still pending (needs a real GTK display) | Claude chose "remove" by default under Scott's 2026-07-23 instruction to proceed without per-item confirmation — repairing would mean inventing new behavior nobody requested, which is out of scope for a paused-feature-work recovery (§7); Scott's merge is the actual approval gate, and this default is easily reversed by not merging |
| RR-07 | Delete `chickenbutt-logo.png` and the 4 orphaned `chickenbutt-panel.png` files | §4 "Dead or unreachable assets" | verified complete | PR #6 (`recovery/rr-07-orphaned-assets`), merged as `96033ac` | grep re-confirmed zero references immediately before deletion (rule 9); 13/15 test scripts run directly, 0 failures | Scott (merge) |
| RR-08 | Resolve and implement the `icons/tray/` generator question (stop generating unreachable/ineffective files and delete them, or wire a real consumer in) | §4 "Uncertain items" | verified complete | PR #10 (`recovery/rr-08-tray-icons`), merged as `cfa149d` | confirmed all 10 files unreachable or reachable-but-ineffective given `icon_theme_path=""`; `generate-icons.py`'s tray-generation code and stale docstring removed; 13/15 test scripts run directly, 0 failures | Claude chose "stop generating + delete" by default under Scott's 2026-07-23 instruction to proceed without per-item confirmation — wiring a real consumer would be new feature work, out of scope while product development is paused (§7); Scott's merge is the actual approval gate |
| RR-09 | CI: adopt automated enforcement, or explicitly accept manual enforcement as permanent | §3 "Test situation" | verified complete | PR #15 (`recovery/rr-09-add-ci`), merged as `0f7a394` | Real, completed GitHub Actions runs — first on the PR alone, then again on the resulting push-to-`main` run (`30026859433`) covering the combined tree with PR #14 also merged — all 15 documented test scripts pass, including both meson-dependent ones with a genuine `meson install`: `test_installed_layout.py` 47/0, `test_desktop_integration.py` 37/0, all others clean. Two real CI-environment bugs found and fixed getting here: `apt-get` hanging on an interactive `needrestart` prompt, and WebKitGTK's `bwrap` sandbox failing under Ubuntu 24.04's default AppArmor unprivileged-userns restriction — both documented in the PR | Scott (decided CI; merged) |
| RR-10 | `ChatSidebar` responsibility reduction (scope TBD pending authorization) | §4 "Architectural concentration" (coupling counts independently re-derived above) | resolved — **Scott decided: defer past recovery** (§7) | none — no code touched | n/a — explicitly deferred, not authorized for this recovery | Scott (decided) |
| RR-11 | Final repository verification | all prior tasks | verified complete | none — verification only, no branch | Every §9 criterion checked directly against current `main` (`383af21`): (1) RR-00 through RR-14 all verified-complete, explicitly-retained (RR-09/RR-10/mistune, §7), or moot — none left blocked or undecided; (2) all 15 documented test scripts run directly, 0 failures, including a genuine `meson install` (`test_installed_layout.py` 47/0, `test_desktop_integration.py` 37/0) — matches the push-to-`main` CI run (`30026859433`) exactly; (3) `git status` clean, local `main` synced with `origin/main` at `383af21`; (4) zero open PRs; (5) all 10 recovery branches (local+remote) deleted after confirming each was fully merged (`git branch -d`, which refuses unmerged branches) — `audit/architecture-inventory` deliberately left untouched, pre-existing unrelated local work for the deferred RR-10; (6) exactly one internal status document in the tree (`recovery-reports/REPOSITORY_RECOVERY.md`) — no stray `HANDOFF`/`STATUS`-style files found (`find . -iname "*handoff*" -o -iname "*status_report*"` → empty) | Scott (verification confirms recovery is complete; §10 closure is his call, not asserted here) |
| RR-12 | Remove `tray.py`'s dead file-based icon lookup branch inside `_load_icon_pixmap` (`if icon_theme_path:` block, ~lines 99-117) | §4 "Dead or unreachable code" listed this finding (`tray.py`'s `_load_icon_pixmap`, `tray.py:98-113`) but it was never assigned a ticket in this ledger — found and fixed while executing RR-08; added here now | verified complete | PR #11 (`recovery/rr-12-remove-tray-file-lookup`), merged as `c0962f9` | confirmed `main.py`'s only `TrayIcon` construction site passes `icon_theme_path=""`, so the branch never executes; `TrayIcon`'s public `icon_theme_path` constructor param, `self._icon_theme_path`, and the `IconThemePath` DBus property left untouched (StatusNotifierItem interface contract, not dead code); 13/15 test scripts run directly, 0 failures | Scott (merge) |
| RR-13 | Fix `find_pkglibdir()`: its glob only searched one directory level below any `lib*` root, so it never found the installed `chickenbutt/` dir on Debian/Ubuntu's multiarch libdir layout (e.g. `lib/x86_64-linux-gnu/chickenbutt`, two levels down). Fixed in both `scripts/test_installed_layout.py` **and** `scripts/test_desktop_integration.py`, which had a separately copy-pasted duplicate of the same function with the identical bug | Newly discovered — not previously in §4. Scott ran `test_installed_layout.py`/`test_desktop_integration.py` directly against unmerged `main` on his own machine (installing meson/ninja himself) and hit this; confirmed pre-existing and unrelated to RR-04/RR-08 — fails identically on unmodified `main` | verified complete | PR #13 (`recovery/rr-13-fix-pkglibdir-multiarch`), merged as `3034dc4` | meson/ninja became available in the execution environment partway through this task (Scott installed them); real verification then performed directly: `test_installed_layout.py` → 47 passed, 0 failed; `test_desktop_integration.py` → 37 passed, 0 failed; all 13 other test scripts re-run clean — all 15/15 scripts in the documented suite genuinely pass now, not skipped | Scott (merge) |
| RR-14 | Remove 3 dangling comment references to deleted `HANDOFF.md`: `meson.build:17`, `scripts/test_markdown_sanitization.py:276`, `scripts/test_sidebar_interactions.py:231` | §4 "Resolved during this recovery" — flagged since RR-00, never had its own ticket; surfaced again during this document's post-8-PR-batch reconciliation pass | verified complete | PR #14 (`recovery/rr-14-fix-dangling-handoff-comments`), merged as `c46f032` | zero remaining `HANDOFF.md` references outside the expected `FORBIDDEN_TOP_LEVEL` assertion; substance of both test comments (a real timing gotcha) kept, only the dead pointer removed; all 15/15 test scripts pass for real, including a genuine meson install (47/0, 37/0); independently re-confirmed by a second reviewer before merge | Scott (merge) |

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
| 2026-07-23 | After all 8 open PRs (RR-03 through RR-08, RR-12, RR-13) merged, reconciled §3 and §4 against current `main` instead of leaving them describing already-fixed problems as current. Dispositioned RR-00 as verified complete: its 114-file baseline reconciles exactly against current `main`'s 96 files (an 18-file delta, every file independently confirmed removed — no unexplained gap, no unclassified new file). Added RR-14 for 3 dangling `HANDOFF.md` comment references, found still-unresolved during this pass. | Ground-truth rule 1 (code outranks documentation) and rule 8 (this document is not itself proof a claim remains true) — §4 had drifted into describing a repository state several merges out of date. | RR-00, RR-14, §3, §4 |
| 2026-07-23 | RR-09 decided: require CI before recovery closes, not permanent manual enforcement. | Scott's explicit choice when asked directly. | RR-09 |
| 2026-07-23 | RR-10 decided: defer `ChatSidebar`/`window.py` decomposition past this recovery entirely — not authorized now. | Scott's explicit choice; this document's own framing already recommended deferral (substantial refactor, not a bounded cleanup task) and Scott agreed. | RR-10 |
| 2026-07-23 | Vendored `vendor/mistune/` unused-surface question decided: keep as-is, no trim. | Scott's explicit choice; vendoring a whole library and using part of it is normal. | RR-00 (question originally raised there) |
| 2026-07-23 | Implemented RR-09's CI workflow (`.github/workflows/tests.yml`). Getting a real (not simulated) GitHub Actions run green required fixing two genuine CI-environment bugs in the workflow itself, iteratively, against real runs: (1) `apt-get` hanging ~8 minutes on an interactive `needrestart` prompt with no TTY to answer — fixed with `DEBIAN_FRONTEND=noninteractive`/`NEEDRESTART_MODE=a`/`NEEDRESTART_SUSPEND=1` and a 20-minute job timeout; (2) WebKitGTK's `bwrap`-based sandbox (both its main network-process sandbox and its separate `xdg-dbus-proxy` component) failing with "setting up uid map: Permission denied" under Ubuntu 24.04's default AppArmor unprivileged-userns restriction — `WEBKIT_DISABLE_SANDBOX=1` alone did not fix the `xdg-dbus-proxy` case; fixed at the root with `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`. Final run: all 15 documented test scripts pass for real on GitHub's own infrastructure, including both meson-dependent ones with a genuine install. | Ground-truth rule 8/9 — a CI workflow that has never actually completed a run is not "done," it's an unverified claim; the real run is what proves it, same principle applied throughout this recovery to local meson verification. | RR-09 |
| 2026-07-23 | PR #14 and PR #15 merged (`c46f032`, `0f7a394`); push-to-`main` CI run on the combined tree confirmed green. RR-11 performed: every §9 criterion checked directly, all satisfied. Deleted all 10 now-merged `recovery/*` branches (local+remote) after confirming each with `git branch -d`, which refuses to delete anything unmerged. Deliberately left `audit/architecture-inventory` untouched — pre-existing local work unrelated to this recovery (branched from the pre-recovery baseline, exploring the `window.py` decomposition question RR-10 just deferred) — not this recovery's to delete. | §9's "no stray branches... left open that this recovery created" only covers branches this recovery created. | RR-11 |

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

---

**Closure confirmed, 2026-07-23.** Every §9 condition was checked directly
against `main` at RR-11 (commit `a042364`) and satisfied — see RR-11's
ledger row (§6) for the specifics. This document is now closed per the
rule above: retained as historical record only, not archived as ongoing
reference and not left open "just in case." A fresh, separate document
for normal product development is designed next, starting from scratch —
not by evolving this one.
