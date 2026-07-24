# ChickenButt Repository Refactor Plan

**This is the single active authority for the refactor effort.** Research
reports under `research/` provide evidence; they do not authorize
implementation on their own. Do not create competing status, handoff, or
roadmap files — update this document instead.

Status as of 2026-07-23: **research complete, through seven rounds of
cross-review, awaiting Scott's decision.** No application code has been
changed. Nothing below is authorized to start until Scott approves it
explicitly.

The phase plan below has gone through seven review rounds, all from
Codex/ChatGPT against the actual source, all independently verified by
Claude before being folded in by checking source claims directly against
`window.py` (and, where a claim was about test behavior, against the
relevant `scripts/test_*.py` file) each round. The full suite was run
once, during round 1, to establish the verified baseline (15/15 passing,
`test_installed_layout.py` 47/47, `test_desktop_integration.py` 37/37,
zero skips); rounds 2-7 were documentation-only revisions with no
application-code changes to re-verify against, so they relied on that
already-established baseline rather than re-running it. See
`research/00-window-audit.md` revision notes for the full findings list
of all seven rounds.
**Round 1** fixed oversized phases (~500-750 method-lines each) and a
monolithic characterization phase. **Round 2** found the round-1 fix had
recreated the same monolithic-test problem in one place, an
underspecified composer extraction interface, two methods assigned to
the wrong owner, three methods miscategorized as mode-agnostic when
they're actually native-transcript rendering, one unsupported cross-phase
dependency, stale line numbers, and wording that treated a forbidden
PR-scope mix as an open option. **Round 3** found the round-2 plan still
inconsistent (test-first was standalone for some phases, bundled for
others), four gaps already named in the audit's own coverage table that
never became actual phases, `_messages` ownership flagged but never
assigned an owner, the native-transcript-adapter move needing an explicit
intent-dispatch interface, and two more extraction seams needing
narrow-interface treatment. **Round 4** found round 3's resolution of
`_messages` ownership described a destination with no migration path
(Phase 18 can't become sole owner while unextracted groups L/M still
mutate the list directly); Phase 16's "report through the window's
sensitivity policy" could have meant literally calling
`_set_load_controls_sensitive`, which touches far more than the
send-button-only behavior it would be replacing; Phase 14 still lacked
the injected-callback treatment already applied elsewhere even though
its methods call `switch_conversation`/`export_conversation`/
`_confirm_delete_conversation` directly; Phases 3 and 9's test scope was
narrower than what Phases 4 and 10 actually move; Phase 19 never required
exercising a *completed* regenerate/continue through to
`_commit_assistant_result`; and the dependency column's exhaustiveness
was ambiguous. **Round 5** found: model-state ownership overlapped across
Phases 8, 10, and 18 (`self._model`/`self._load_failed` are written by
both Phase 8's and Phase 10's methods, while Phase 18 was also described
as owning the conversation's "model"); round 4's claim that Phase 22
could cleanly remove the `_messages` facade was false, since read-only
consumers exist in methods belonging to earlier phases (4, 8, 10, and 18
itself), and the same pattern applies to `_health`/`_loading_model`/
`_load_failed`/`_model`/`_ollama_cli_busy`, which `_send` (Phase 22) reads
directly; and this file's own intro overstated the verification history
(the suite was run once, not "each time"). **Round 6** found: Phase 11's
test scope (four native message-row methods) didn't match Phase 12's
actual breadth (the full `TranscriptSink` contract — reset/empty-state,
replay, removal, status-message create/update, greeting, streaming
update/finalization); `_greeted_models` was misattributed in the state
inventory and had no assigned owner despite being split between group F
(clears it) and group J (reads/mutates it); Phases 13/14 were
under-specified (three of Phase 14's eight methods and the
`_history_dirty` short-circuit had no test coverage, and three presenter
callbacks weren't enough given `_refresh_chat_title`'s direct state reads
and `_history_dirty`'s unassigned ownership); Phase 18's facade was
described as read-only when group L's call sites require whole-list
reassignment; and round 5's own reader inventory had misattributed two
citations (`_composer_hint_should_show` and `_show_ephemeral_greeting`
are retained on `ChatSidebar`, not living inside the phases they were
credited to). **Round 7** found the largest set of issues yet: the
transcript-adapter phase was itself oversized (13 methods, ~705
method-lines including the 254-line `_start_assistant_stream` — measured
directly) and had to be split into three test/extract pairs; several
characterization phases still didn't protect everything their paired
extraction moved (health/probe's `_on_health_action`/`_preferred_model`,
all eight of the CLI-command methods, and — most significantly — `_send`
itself, which the streaming characterization never covered at all,
confirmed by `test_generation_lifecycle.py`'s own docstring stating it
"mirrors" `_send` while explicitly skipping its guards); the
conversation-lifecycle characterization was missing a real
persistence-failure-ordering asymmetry (`switch_conversation` continues
past a `set_active` failure, `delete_conversation` aborts past a store
failure); message-ID allocation (`_next_msg_id`/`_msg_counter`) was
misassigned to message actions when its real callers span four other
phases; the sidebar-extraction phase had two factual errors (claiming
model-load state was still window-owned when its owner phase precedes it
in sequence, and misattributing `_history_dirty`'s write sites); and the
conversation-lifecycle phase's own reader-migration list, added in round
6, was still missing four consumers. Every one of those was verified
directly against the code before being folded in — including measuring
every method in the transcript-adapter phase, re-reading
`test_generation_lifecycle.py`'s own docstring, and tracing every
`_next_msg_id` call site. Given how many rounds running had found the
same class of cross-phase attribution error, round 7 also adds the
**ownership/migration matrix** below, so these relationships are checked
mechanically instead of re-derived from prose each round. **What's
actually agreed right now:** the findings from all seven rounds, and the
general direction (standalone characterization phase before every
extraction with no exceptions, exact behavior preservation with nothing
folded into an extraction PR, explicit ownership/interfaces — including
staged migrations governed by a general invariant where an immediate
cutover isn't possible — for every seam this audit found ambiguous).
**What's not yet locked:** the precise phase table is now on its seventh
revision and may see further changes if another review pass finds
something; treat it as the current best draft, not a settled agreement,
until it survives a review round with no further findings.

## Objective

Make the surviving codebase easier to understand, test, change, and
maintain without changing product behavior accidentally. First target:
`window.py` / `ChatSidebar` (3,753 lines, ~99 methods, currently the only
part of the codebase without a clear ownership seam — see
`research/00-window-audit.md`).

## Ground rules (carried from the kickoff, restated here so this file is
self-contained)

- Current code and test behavior outrank documentation.
- One concern per PR: never mix behavior change, feature work, cleanup,
  and structural extraction in the same PR.
- No wholesale rewrite of `window.py`.
- Preserve observable behavior unless Scott separately authorizes a
  behavior change.
- Extract by responsibility and ownership, not by line-count targets.
- Add characterization tests before moving behavior that isn't already
  protected by one.
- Every implementation PR runs the complete documented 15-script suite;
  the Meson-backed tests must genuinely run — "SKIPPED" is not a pass.
- GitHub Actions must pass on the exact reviewed PR head.
- After a merge: confirm `main` is clean, synced with origin, and CI
  passes on the combined tree — then update the ledger below.
- Do not modify `recovery-reports/REPOSITORY_RECOVERY.md` as part of this
  work; it's retired.

## Claude/Codex coordination

For each task, one of Claude or Codex is researcher/implementer and the
other is independent reviewer; roles can switch between tasks. Never both
editing the same branch at once. The reviewer inspects the actual diff
and reruns the tests themselves — a clean review does not itself
authorize a merge. Every merge decision is presented to Scott (reviewed
head SHA, test results, risks, recommendation) and requires his explicit
go-ahead.

---

## Proposed phase sequence (from `research/00-window-audit.md` §7, round 7)

Ordered lowest-coupling/highest-existing-coverage first so the extraction
pattern is proven before it's applied to the most entangled groups. Every
extraction phase has its own standalone characterization phase
immediately before it — no bundled exceptions, **26 phases in 13
test/extract pairs** (the transcript-adapter phase pair from round 6 is
now three pairs, per round 7's finding that it was itself oversized).
None of these are approved yet — this table exists so Scott can approve,
reorder, split, or reject phases individually; he may also choose to
merge a test phase and its following extraction phase into one reviewed
PR at approval time where the combined diff stays small (see audit §7
closing note) — that's a PR-packaging choice, not a change to whether the
test must exist first.

**"Depends on" lists ordering/interface prerequisites, not every
collaborator a phase's code calls** — `_send` (Phase 26) alone touches
roughly seven other phases' interfaces; an exhaustive column would be
noise. Specific omissions that change a phase's design are called out in
its prose in the audit instead (e.g. Phase 20 needing a hook into Phase
8's territory for a post-pull refresh). **The ownership/migration matrix
below is the mechanically-checkable complement to this column** — use it,
not the table, to verify a specific piece of shared state end-to-end.

**General migration invariant, applying to every staged migration in
this plan** (added in round 5, after the streaming phase's original
facade-removal claim was found false): an extracted owner exposes
read-only queries or delegating compatibility properties for consumers
that haven't migrated yet, rather than requiring atomic migration;
mutable state is never copied or duplicated between owners; a facade is
removed only after a direct-reference inventory across the *whole file*
— not just the phases assumed to touch it — proves zero remaining
consumers.

| # | Phase | Depends on | Risk | Approved? |
|---|---|---|---|---|
| 1 | Settings characterization (test-only) — covers *every* moved behavior: read/write-failure handling, `_load_last_model`, `_save_last_model` whitespace/no-op, `_pick_startup_model` | — | n/a | Not yet |
| 2 | Settings extraction (group A subset) → own module | Phase 1 | Negligible | Not yet |
| 3 | Composer geometry characterization (test-only) — full scope of Phase 4's move: sizing, char-cap truncation, placeholder visibility, scrollbar-policy transitions, the alignment-callback interaction | — | n/a | Not yet |
| 4 | Composer geometry/character-cap extraction *only* — explicit interface for `_placeholder` injection, `_composer_truncating`/`_composer_layout_hooked` ownership, and the alignment callback | Phase 3 | Low | Not yet |
| 5 | Export characterization (test-only) | — | n/a | Not yet |
| 6 | Export extraction via an **injected title provider** — `_conversation_display_title` stays conversation-owned (shared with delete-confirm), export takes a `title_provider` callback instead of owning or reaching back for it (**this callback gets re-bound in Phase 22, per its round-7 correction**) | Phase 5 | Low-medium | Not yet |
| 7 | Health/probe characterization (test-only) — **all of group I**: `_apply_health`/probe ordering, **plus `_on_health_action`'s three branches, `_preferred_model`, and model-selection edge cases, all confirmed untested** | — | n/a | Not yet |
| 8 | Health/probe extraction (group I), **excluding** `_set_load_controls_sensitive` and **not claiming ownership of `_model`/`_loading_model`/`_load_failed`/`_load_generation`** — reports via callbacks into whatever currently owns model-session state (window-owned until Phase 10) | Phase 7 | Medium | Not yet |
| 9 | Model-load characterization (test-only) — stale-load ordering, **plus** `_update_load_progress`'s NDJSON mapping and `_on_model_load_finished`'s success/failure completion UI, **plus greeting-dedup behavior across repeated loads** | — | n/a | Not yet |
| 10 | Model-load extraction (group J), **excluding** `_set_load_controls_sensitive` and `_show_ephemeral_greeting`, and **becoming the sole canonical owner of model-session state** (`_model`/`_loading_model`/`_load_failed`/`_load_generation`, **and `_greeted_models`**, verified two-owner overlap with group F — this phase exposes `reset_greetings()` for the conversation-lifecycle phase) — migrates Phase 8's already-extracted callbacks onto this new interface | Phase 8, Phase 9 | Medium | Not yet |
| 11 | Transcript reset/replay/removal characterization (test-only) — first of three native-transcript slices (**round 7: split from one oversized pair — 13 methods, ~705 lines, incl. the 254-line `_start_assistant_stream`, measured directly**) | — | n/a | Not yet |
| 12 | Transcript adapter seam: reset, replay, removal — incl. `_native_remove_message` (pure rendering, no message-action calls) | Phase 11 | Medium | Not yet |
| 13 | Status-message and greeting characterization (test-only) — second slice: CLI status-bubble create/update, ephemeral greeting, both backends | — | n/a | Not yet |
| 14 | Transcript adapter seam: status messages and greeting — rewires `_post_status_message`/`_update_status_message`/`_show_ephemeral_greeting`'s internal branching without moving those methods' ownership | Phase 12, Phase 13 | Medium | Not yet |
| 15 | Streaming-update/finalization and native-intent characterization (test-only) — third and riskiest slice: `_start_assistant_stream`'s flush/finalize posting, `_append_message`/`_native_action_bar`/`_native_edit_user` | — | n/a | Not yet |
| 16 | Transcript adapter seam: streaming updates/finalization and native intent dispatch — **`_native_action_bar`/`_native_edit_user` reworked to emit intents through an injected callback** (mirroring `_on_web_intent`) instead of calling group-L methods or reading `_messages` directly | Phase 12, Phase 15 | Medium-high (riskiest of the three adapter slices) | Not yet |
| 17 | Sidebar/history-UI characterization (test-only) — **all eight of Phase 18's methods**, not just the popover: `_refresh_chat_title` (incl. its loading/streaming guard), `_select_active_history_row`, `_on_history_row_activated`, and the `_history_dirty` short-circuit, none of which have any existing coverage | — | n/a | Not yet |
| 18 | Sidebar/history-UI extraction (group E), via **injected presenter callbacks** (`on_activate`/`on_export`/`on_delete`, **re-bound in Phase 22 once their targets move**) **plus status accessors** — **`is_loading_model()` consumes Phase 10's real interface immediately** (round 7 correction: Phase 10 precedes this phase, it is not a placeholder), while `is_streaming()`/`get_active_conversation_id()` are genuinely still window-owned until Phases 26/22 — **and explicit `_history_dirty` ownership** (round 7 correction: the actual write sites are group C/E setup and `_mark_history_dirty` itself; group F only *calls* that method) — no transcript dependency (verified: zero `_web`/`chat_box`/`_transcript_mode` references in any of its 8 methods) | Phase 17 | Medium | Not yet |
| 19 | Composer-CLI-command characterization (test-only) — **all eight methods Phase 20 moves**, not just three: busy-state sensitivity, pull-progress formatting, status create/update, error handling, successful-pull-triggers-refresh | — | n/a | Not yet |
| 20 | Composer-CLI-command extraction (group K) — CLI controller owns only the busy flag, reports it through a **new, narrow `on_cli_busy_changed(bool)` callback that reproduces today's send-button-only behavior** (not a call to `_set_load_controls_sensitive`, which touches far more widgets); also needs an `on_pull_succeeded` hook for the model-refresh call currently made directly | Phase 8, Phase 14, Phase 19 | Low-medium | Not yet |
| 21 | Conversation-lifecycle characterization (test-only) — `new_chat`/`clear_chat`/`delete_conversation`/`_confirm_delete_conversation`, currently untested at the `ChatSidebar` level, **plus the persistence-failure-ordering asymmetry**: `switch_conversation` continues past a `set_active` failure while `delete_conversation` aborts past a store failure — confirmed via exact except-block behavior | — | n/a | Not yet |
| 22 | Conversation-lifecycle extraction (group F) — **establishes the canonical in-memory active-conversation projection (conversation ID + messages *only*)** via a staged migration: `ConversationStore` stays canonical persisted storage; this phase owns the projection + a **getter-and-setter** compatibility facade (a getter alone can't support group L's whole-list reassignment call sites); **migrates every currently-known read-only `_messages` consumer**, **now including** the transcript-adapter's `current_text()` accessor, Phase 8's `_preferred_model`, Phase 18's active-ID accessor, and Phase 6's title-provider callback (round 7 additions — all confirmed consumers the round-6 list missed), plus re-pointing Phase 18's `on_activate`/`on_delete` callbacks to this phase's own object; **also becomes the owner of message-ID allocation** (`_next_msg_id`/`_msg_counter` — round 7 correction: these were misassigned to message actions; real callers are this phase, CLI, streaming, and native rendering, never group L) and **must explicitly preserve `_history_restored`** (write-only, never read, dropping it would be cleanup mixed into extraction) and **the persistence-failure-ordering asymmetry from Phase 21** | Phase 12, Phase 21 | Medium-high | Not yet |
| 23 | Message-action characterization (test-only, group L, both transcript modes) — **including a direct test of `_on_web_intent` dispatch routing, and completed (not cancelled) regenerate/continue commits through `_commit_assistant_result`** (confirmed: `test_generation_lifecycle.py` has zero `"replace"`/`"continue"`/`_commit_assistant_result` references) | Phase 11/15 (as template) | n/a | Not yet |
| 24 | Message-action extraction (group L, native-rendering **and message-ID allocation excluded** — both belong elsewhere per round 7) — **migrates onto Phase 22's interface** (facade not yet removed; group M still uses it) | Phase 16, Phase 22, Phase 23 | Medium-high | Not yet |
| 25 | Streaming characterization (test-only) — non-cancellation error paths mid-stream, **plus `_send` itself** (round 7 correction: `test_generation_lifecycle.py`'s own helper docstring says it "mirrors" `_send` while explicitly skipping its composer/health/model guards — `_send` has zero direct coverage, not just thin coverage): empty-input guard, busy guards, composer-command routing, unhealthy-reprobe, missing-model guard, successful append/persist/start ordering | — | n/a | Not yet |
| 26 | Streaming-engine extraction (group M), last — migrates onto Phase 22's interface; since Phase 22 already migrated every other reader, this phase's facade removal is now genuinely clean (group M was the last remaining raw consumer) | Phases 12-16, 22, 24, 25 (and in practice 8, 10, 20, since `_send` calls into all of them) | High | Not yet |

A firm rule applies to every phase above, not an open choice: each one
preserves current behavior exactly, including behavior this audit found
questionable (`_on_ollama_probe`'s missing generation guard, the
four-flag sensitivity logic, the switch/delete persistence-failure
asymmetry). Fixing any of those is never a sub-option folded into an
extraction PR — the ground rules already forbid mixing behavior change
with structural extraction.

Two structural questions are deliberately left open for Scott rather
than decided in the audit (see audit §8):

1. Should the sensitivity "state machine" (four busy flags computed in
   four places — audit §5 risk 3) or `_on_ollama_probe`'s missing
   generation guard (audit §4.3) ever be *fixed*, as a wholly separate,
   explicitly authorized PR after the relevant extraction phase lands —
   or left as-is indefinitely? (Not: fixed *during* the extraction — that
   part isn't optional.)
2. Phase 16 requires *targeted* native-mode tests (Phases 11/13/15) —
   three existing tests cannot simply be re-run under
   `CHICKENBUTT_TRANSCRIPT=native` (they hard-require the WebKit view and
   would fail). Does Scott want a standing native-mode CI lane beyond
   those targeted tests, or is manual verification enough for now?

## Ownership/migration matrix

Added in round 7 because prose revisions had, by that point, missed the
same class of cross-phase attribution error across six rounds running.
This table is the mechanically-checkable complement to the phase table
and the "Depends on" column: one row per shared capability, so a claim
like "Phase X owns Y" or "Phase Z consumes W's interface" can be checked
against a single row instead of re-derived from scattered prose. When
revising this plan, update this table and the phase table together — a
mismatch between them is itself a bug in the plan.

| Capability | Current writers/readers | Canonical owner phase | Pre-owner compatibility interface | Later consumers requiring rewiring | Facade-removal phase | Characterization coverage |
|---|---|---|---|---|---|---|
| **Messages / active conversation ID** (`self._messages`, `self._conversation_id`) | Written: F (clear/new/switch/restore), L (delete/drop/regenerate/edit-resend), M (send/commit). Read: D (`_composer_hint_should_show`), I (`_select_model_name`/`_on_model_selected`/`_on_ollama_probe`/`_on_health_action`/`_preferred_model`), J (`_on_model_load_finished`/`_show_ephemeral_greeting`), E (`_rebuild_history_list`/`_select_active_history_row`), C (`_build_ui` reads `_conversation_id` in its export-action closures, `window.py:720`/`726` — added: a retained reader earlier revisions omitted), transcript adapter's `current_text()`, export's `title_provider` | **Phase 22** | Getter-*and-setter* facade property on `ChatSidebar._messages`; `_conversation_id` a plain attribute until Phase 22 | Composer hint (retained method, migrated in-place by Phase 22), `_build_ui`'s export-action closures (retained, migrated in-place by Phase 22), health/load callback wiring (Phases 8/10), sidebar accessor (Phase 18), transcript adapter's `current_text()` (Phase 16), export's `title_provider` (Phase 6) | **Phase 26** (once groups L/M, the only mutators, are migrated) | Phase 21 (incl. persistence-failure-ordering asymmetry) |
| **Message-ID allocation** (`_next_msg_id`, `_msg_counter`) | Called from F (`_apply_restored_transcript`), K (`_post_status_message`), M (`_send`, `_start_assistant_stream`), native rendering (`_append_message`) — **never L** | **Phase 22** | Plain `ChatSidebar` method (`_next_msg_id`) unchanged until Phase 22 | Phases 16/20/26's already-extracted objects' calls re-pointed to the new owner | N/A (thin delegator retained, not a raw-attribute facade) | Format guarantees (`{prefix}-{counter}-{uuid suffix}`) added to Phase 21's test scope |
| **Model session** (`_model`, `_loading_model`, `_load_failed`, `_load_generation`) | Written by I (`_select_model_name`/`_on_model_selected`/`_on_ollama_probe`) and J (`_on_model_load_finished`, **and `_begin_model_load`** — corrected: `_begin_model_load` writes `_loading_model` (`window.py:2695`), `_load_failed` (`2696`), and is the **sole non-`__init__` writer of `_load_generation`** (`+= 1`, `2693`), the by-value-captured concurrency counter of §4.3; earlier revisions omitted it from this cell entirely) | **Phase 10** | I's methods use callbacks into `ChatSidebar` until Phase 10 lands, then Phase 10 migrates that wiring | Sidebar's `is_loading_model` (Phase 18, consumes directly — Phase 10 precedes it), streaming's guards (Phase 26) | N/A (Phase 10 becomes owner outright in its own phase) | Phase 9 (stale-load ordering + completion UI) |
| **Greeting deduplication** (`_greeted_models`) | Cleared by F (clear/new/switch); read + mutated only by J (`_on_model_load_finished`) — I never touches it | **Phase 10** | Plain attribute until Phase 10 | Phase 22 calls `reset_greetings()` on every conversation transition | N/A (Phase 10 owns outright) | Phase 9 (added round 7) |
| **Health** (`_health`, `HealthState`) | Written by I (`_apply_health`); read by M (`_send` checks `can_chat`) | **Phase 8** | N/A — I owns outright once extracted | `_send`'s reprobe check (Phase 26, consumes directly since Phase 8 precedes it) | N/A | Phase 7 (incl. `_on_health_action`, `_preferred_model` — round 7 additions); `_send`'s reprobe branch added to Phase 25 |
| **Streaming state** (`_streaming`, `_stream_generation`, `_active_stream_cancel`) | Written by M; read by F/L/E's guard checks **plus four further reader methods earlier revisions omitted** (six read sites, all on `_streaming`): J's `_begin_model_load` (`window.py:2688`), K's `_set_composer_cmd_busy` (`2955`), N's `_set_status` (`2372`), and the shared, window-owned sensitivity policy `_set_load_controls_sensitive` (`2560`, `2563`, `2573`) | **Phase 26** (last) | Plain attribute for everyone until Phase 26; F/L/E's already-extracted objects read via callback into `ChatSidebar` the whole time | F's guards (Phase 22), L's guards (Phase 24), E's `is_streaming` (Phase 18) — all migrated by Phase 26. **Plus the four readers above:** J needs streaming-state access once extracted at **Phase 10**; K's **Phase 20** `on_cli_busy_changed` callback must reproduce today's behavior *using streaming state*; `_set_status` is **not** moved by transcript Phases 12-16 — its streaming-state transition belongs to **Phase 26**; `_set_load_controls_sensitive` stays window-owned but will need access to Phase 26's streaming owner | **Phase 26** (last phase, nothing after it) | `test_generation_lifecycle.py` — strongest-covered state in the file; `_send`'s own guard added in Phase 25 |
| **CLI busy state** (`_ollama_cli_busy`) | Written + read only by K; consumed for gating in `_send` | **Phase 20** | Dynamically-created plain attribute until Phase 20 | `_send`'s busy-check (Phase 26, consumes directly) | N/A (Phase 20 owns outright) | Phase 19 (widened, round 7) |
| **History-dirty state** (`_history_dirty`) | Raw assignments in `__init__`/`_build_ui` (group C) and `_mark_history_dirty`/`_rebuild_history_list` (group E) — **group F never assigns directly, only calls `_mark_history_dirty()`** (round 7 correction to round 6's evidence) | **Phase 18** | Plain attribute/method until Phase 18 | Group F's calls to `_mark_history_dirty()` stay as plain calls into the new sidebar object until Phase 22 extracts F itself | N/A (Phase 18 owns outright) | Phase 17 (the short-circuit itself, not just setting the flag) |
| **Transcript presentation** (`_transcript_mode` branch; `_web`/`chat_box`; status/greeting rendering; streaming update posting) | Touched by C, F, K, L (removal), M (streaming), native action-bar/edit/remove | **Phases 12/14/16** (three-way split, round 7) | N/A — this is the interface-introduction itself | F (Phase 22), K (Phase 20), L (Phase 24), M (Phase 26) all consume the finished `TranscriptSink` once their own phase runs (ordering already ensures adapter phases precede all four) | N/A (seam introduction, not a migration-with-facade) | Phases 11/13/15 (three slices, round 7 split) |
| **Sensitivity policy** (`_set_load_controls_sensitive`, composer/nav/sidebar enablement) | **Current callers are exclusively I/J** (four call sites): I's `_refresh_models` (`window.py:2417`) and `_on_ollama_probe` (`2468`); J's `_show_load_overlay` (`2618`) and `_hide_load_overlay` (`2651`). **K does not call it today** — corrected: earlier revisions listed K in this "current" column, but K's Phase-20 narrow `on_cli_busy_changed` callback is *proposed* design, not current state, and per the CLI-busy row it deliberately does **not** call `_set_load_controls_sensitive` (which touches far more widgets than K's send-button-only behavior) | **Deliberately unresolved** — §5 risk 3, a decision for Scott | N/A | N/A until Scott authorizes a consolidation phase | N/A | None directly; exercised only incidentally through Phases 7-10/19-20's tests — flagged as a known gap, out of scope for these 26 phases |
| **Status/title presentation** (`_conversation_display_title`, `_refresh_chat_title`, `_set_status`) | `_conversation_display_title` read by export (Phase 6) and delete-confirm (Phase 22); `_refresh_chat_title` (Phase 18) reads `_loading_model`/`_streaming`/`ConversationStore`/`_conversation_id`; `_set_status` (Phase 26) falls back to `_refresh_chat_title` | `_conversation_display_title` → **Phase 22**; `_refresh_chat_title` → **Phase 18** | Export's `title_provider` callback (Phase 6) bound to `ChatSidebar._conversation_display_title` until Phase 22 | Export's `title_provider` re-bound once Phase 22 lands; `_refresh_chat_title`'s accessors migrated per the model-session/streaming-state rows above | N/A | Phase 17 (round 7 addition — `_refresh_chat_title` was previously untested) |

## Decisions log

- 2026-07-23 (round 1) — Codex reviewed Claude's initial 7-phase draft
  and found it correct on the architectural diagnosis but flawed in
  execution (oversized phases, a monolithic characterization phase,
  several factual overstatements). Claude verified every finding against
  the source and test suite and folded in corrections.
- 2026-07-23 (round 2) — Codex reviewed the round-1 revision and found
  further problems (detailed in the audit's round-2 revision note).
  Claude again verified every finding directly against the source before
  folding it in.
- 2026-07-23 (round 3) — Codex reviewed the round-2 revision and found:
  inconsistent test-first application (Phases 1-5 bundled, later phases
  didn't), four documented-but-unaddressed coverage gaps, unresolved
  `_messages` ownership, an underspecified intent interface for the
  native transcript adapter, and two more extraction seams needing
  narrow-interface treatment. Claude verified every finding directly
  against the source (including re-checking `test_generation_lifecycle.py`
  for `OllamaError` coverage, and the exact bodies of
  `_native_action_bar`/`_native_edit_user`/`_set_composer_cmd_busy`/
  `_safe_export_basename`) before folding it in.
- 2026-07-23 (round 4) — Codex reviewed the round-3 revision and found:
  Phase 18's `_messages`-ownership resolution had no migration path (it
  can't become sole owner while unextracted groups L/M still mutate the
  list directly); Phase 16's sensitivity-callback wording could have
  meant an accidental behavior change (`_set_load_controls_sensitive`
  touches far more than `_set_composer_cmd_busy` does today); Phase 14
  needed the injected-callback treatment already used elsewhere; Phases 3
  and 9 under-scoped their test coverage relative to what Phases 4 and 10
  actually move; Phase 19 never required exercising a completed
  regenerate/continue through `_commit_assistant_result`; and the
  dependency column's exhaustiveness was ambiguous. Claude verified every
  finding directly against the source (including re-reading
  `_run_ollama_pull`'s completion callback and
  `_on_history_row_activated`'s body, and re-confirming zero
  `"replace"`/`"continue"`/`_commit_assistant_result` references in
  `test_generation_lifecycle.py`) before folding it in.
- 2026-07-23 (round 5) — Codex reviewed the round-4 revision and found:
  model-state ownership overlapping across Phases 8, 10, and 18
  (`self._model`/`self._load_failed` written by both Phase 8's and Phase
  10's methods, while Phase 18 also claimed the conversation's "model");
  round 4's Phase 22 facade-removal claim was false, since read-only
  `self._messages` consumers exist in methods belonging to earlier phases
  (4, 8, 10, 18), with the same pattern applying to
  `_health`/`_loading_model`/`_load_failed`/`_model`/`_ollama_cli_busy`;
  and this file's intro overstated the verification history (suite run
  once, not "each time"). Claude verified every finding directly against
  the source (including re-confirming every `self._model =` write site
  and every `self._messages`/`not self._messages` read site across the
  whole file) before folding it in.
- 2026-07-23 (round 6) — Codex reviewed the round-5 revision and found:
  Phase 11's characterization scope didn't match Phase 12's actual
  breadth (four native methods vs. a full `TranscriptSink` contract
  spanning 12+ call sites); `_greeted_models` was misattributed in the
  state inventory as "written by groups I/J" with no assigned owner,
  when it's actually a group-F/group-J overlap; Phases 13/14 were
  under-specified (three of Phase 14's eight methods and the
  `_history_dirty` short-circuit had zero test coverage, and three
  presenter callbacks weren't enough given `_refresh_chat_title`'s direct
  state reads); Phase 18's facade was described as read-only when group
  L's call sites require whole-list reassignment; and round 5's own
  reader inventory had misattributed `_composer_hint_should_show` and
  `_show_ephemeral_greeting` to phases whose own text explicitly excludes
  them (they're retained on `ChatSidebar`). Claude verified every finding
  directly against the source (including re-reading Phase 4's and Phase
  10's own exclusion text, every `_greeted_models`/`_history_dirty`
  read/write site, and the exact `_messages` reassignment call sites)
  before folding it in.
- 2026-07-23 (round 7) — Codex reviewed the round-6 revision and found
  six issues, the largest set yet: the transcript-adapter phase was
  itself oversized (13 methods, ~705 method-lines, incl. the 254-line
  `_start_assistant_stream` — measured directly) and needed a three-way
  split into test/extract pairs, not just a PR-packaging option; several
  characterization phases still didn't protect everything their paired
  extraction moved (health/probe's `_on_health_action`/`_preferred_model`;
  all eight CLI-command methods vs. three named; and `_send` itself,
  which the streaming characterization never covered — confirmed via
  `test_generation_lifecycle.py`'s own docstring stating it "mirrors"
  `_send` while explicitly skipping its guards); the conversation-lifecycle
  characterization was missing a real persistence-failure-ordering
  asymmetry (`switch_conversation` continues past a `set_active` failure,
  `delete_conversation` aborts past a store failure); message-ID
  allocation was misassigned to message actions when its real callers
  span four other phases; the sidebar-extraction phase had two factual
  errors (claiming model-load state was still window-owned when its owner
  phase precedes it, and misattributing `_history_dirty`'s write sites to
  group F instead of group C/E); and the conversation-lifecycle phase's
  own reader-migration list was still missing four consumers. Claude
  verified every finding directly against the source (including measuring
  every method in the transcript-adapter phase, re-reading
  `test_generation_lifecycle.py`'s own docstring, confirming the exact
  except-block behavior in `switch_conversation`/`delete_conversation`,
  and tracing every `_next_msg_id` call site) before folding it in. Given
  how many rounds running had found the same class of cross-phase
  attribution error, this round also adds the **ownership/migration
  matrix** above, so these relationships can be checked mechanically
  rather than re-derived from prose each round. **Consensus so far covers
  the findings from all seven rounds and the general revision direction;
  it does not yet cover the precise 26-phase table as final** — that
  table is the current best draft and remains open to a further review
  round. No phase is approved for implementation until Scott says so,
  independent of whether the research documents reach a stable state.

## Refactor ledger

*(Empty — fills in after each phase merges: PR link, merge SHA, tests
run, any remaining limitations. One entry per completed phase, oldest
first.)*
