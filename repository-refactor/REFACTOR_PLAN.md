# ChickenButt Repository Refactor Plan

**This is the single active authority for the refactor effort.** Research
reports under `research/` provide evidence; they do not authorize
implementation on their own. Do not create competing status, handoff, or
roadmap files — update this document instead.

Status as of 2026-07-23: **research complete through ten review rounds;
implementation has begun.** Phase 1 is merged and verified. It added
characterization tests only; no application code has changed. Unstarted
phases remain proposals until work begins on their bounded phase branch.

The phase plan below has gone through ten review rounds. Rounds 1-7
were Codex/ChatGPT reviews against the actual source, independently
verified by Claude before being folded in by checking source claims
directly against `window.py` (and, where a claim was about test behavior,
against the relevant `scripts/test_*.py` file). Round 8 was an independent
browser-GPT review of immutable published commit `6040d39`, followed by
local Codex verification of every candidate finding against the clean,
synchronized checkout; six structural findings were confirmed, while
the proposed settings finding was reclassified as useful enumeration
already covered by Phase 1's exhaustive requirement, not a blocker. The
full suite was run once, during round 1, to establish the verified
baseline (15/15 passing, `test_installed_layout.py` 47/47,
`test_desktop_integration.py` 37/37, zero skips); rounds 2-10 were
documentation-only revisions with no application-code changes to
re-verify against, so they relied on that already-established baseline
rather than re-running it. See `research/00-window-audit.md` revision
notes for the full findings list of all ten rounds.
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
mechanically instead of re-derived from prose each round. **Round 8**
found six more structural gaps in Phases 3-10: the Phase-10
`_greeted_models` ownership interval was invalid until Phase 22; the
model-session compatibility inventory omitted live consumers and any
removal lifecycle; three loader-private state fields and their behavior
were missing from Phases 9/10; Phase 8's callback/provider contract and
`_suppress_model_select` ownership were incomplete; export omitted
dialog/write branches and a caller/delegator lifecycle; and composer
geometry omitted its window-geometry providers and build-time signal
migration. The browser reviewer also proposed more settings assertions,
but local verification found that Phase 1 already requires every moved
settings behavior and Phase 2 already preserves re-export compatibility,
so that item is precision guidance rather than a seventh structural
defect. **Round 9** independently audited Phases 11-20 against published
commit `4473906`, then locally verified eight candidate findings: the
three transcript slices lacked a dependency-closed primitive, staged
state owner, and inbound compatibility lifecycle; Phase 16 lacked an
opaque native-stream identity protocol; forced WebKit-to-native fallback
was uncharacterized; Phase 18 omitted sidebar-private state, construction
wiring, and retained callers; and Phases 19/20 had an invalid CLI
ownership interval plus an incomplete controller/test contract.
**Round 10** audited Phases 21-26 locally after a remote candidate report.
It rejected redundant pruning/greeting-reset additions and an unsupported
concurrent-ID guarantee, but found six real gaps the remote pass missed:
Phase 21 did not fully characterize the lifecycle helpers Phase 22 moves;
Phases 22, 24, and 26 omitted inbound caller/delegator lifecycles; Phase
23 did not enumerate all eight moved message-action methods and their
branches; and Phase 25 omitted buffer/transcript ordering in `_send`.
**What's agreed:** the findings from all ten rounds and the 26-phase
implementation sequence below: standalone characterization before every
extraction, exact behavior preservation, explicit ownership/interfaces,
and staged migrations governed by a general invariant where immediate
cutover is not possible. Phase 1 is complete. The remaining phase rows
stay proposals until started, and the combined result receives a
comprehensive audit after all phases are complete.

## Objective

Make the surviving codebase easier to understand, test, change, and
maintain without changing product behavior accidentally. First target:
`window.py` / `ChatSidebar` (3,753 lines, ~99 methods, currently the only
part of the codebase without a clear ownership seam — see
`research/00-window-audit.md`).

## Ground rules (carried from the kickoff, restated here so this file is
self-contained)

- Current code and test behavior outrank documentation.
- One concern per implementation PR: never mix behavior change, feature
  work, cleanup, and structural extraction in the same PR.
- No wholesale rewrite of `window.py`.
- Preserve observable behavior unless Scott separately authorizes a
  behavior change.
- Extract by responsibility and ownership, not by line-count targets.
- Add characterization tests before moving behavior that isn't already
  protected by one.
- Every implementation PR runs the complete documented 15-script suite;
  the Meson-backed tests must genuinely run — "SKIPPED" is not a pass.
- GitHub Actions must pass on the exact reviewed PR head.
- After a phase merge: confirm `main` is clean and synced with origin, and
  that CI passes on the combined tree — then replace that phase's proposal
  in the phase table with its verified completion report.
- Do not modify `recovery-reports/REPOSITORY_RECOVERY.md` as part of this
  work; it's retired.

## Implementation coordination

Documentation-only audit findings and plan corrections do not require a
PR. After their factual basis and diff are checked, they may be committed
directly to `main` with Scott's authorization.

Use one short-lived branch and one PR per phase, created sequentially from
the clean, synchronized `main` produced by the preceding phase. A single
Codex working session may implement and review that phase. Its explicit
review must inspect the actual diff and rerun the required tests; exact-head
GitHub Actions must also pass. A clean review does not itself authorize a
merge: Scott must authorize the phase merge, either specifically or through
advance conditional authorization. After all phases are complete, perform
a comprehensive audit of the combined refactor and resolve any findings in
new bounded PRs.

---

## Phase sequence (from `research/00-window-audit.md` §7, round 10)

Ordered lowest-coupling/highest-existing-coverage first so the extraction
pattern is proven before it's applied to the most entangled groups. Every
extraction phase has its own standalone characterization phase
immediately before it — no bundled exceptions, **26 phases in 13
test/extract pairs** (the transcript-adapter phase pair from round 6 is
now three pairs, per round 7's finding that it was itself oversized).
Phase 1 is complete. Unstarted rows remain proposals that Scott may
approve, reorder, split, or reject. He may also choose to merge a test
phase and its following extraction phase into one reviewed PR where the
combined diff stays small (see audit §7 closing note) — that is a
PR-packaging choice, not a change to whether the test must exist first.

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

| # | Phase | Depends on | Risk | Status |
|---|---|---|---|---|
| 1 | **Completed 2026-07-23** — Settings characterization (test-only), [PR #16](https://github.com/scottonanski/ChickenButt/pull/16), merge `fae375b748814c657615b616cdcd9d4c3bb27119`. Actual scope: 22 settings assertions added to `scripts/test_sidebar_interactions.py`; no production-code changes. Verification: targeted test 59/0; all 15 documented scripts passed locally, including Meson-backed 47/0 and 37/0 checks with no skips; exact-head PR `Tests` CI and synchronized-`main` [CI run 30069334589](https://github.com/scottonanski/ChickenButt/actions/runs/30069334589) passed. Preserved guarantee: current settings read/write-failure handling, last-model load/save whitespace and no-op semantics, and startup-model exact/soft/fallback selection are locked before extraction. Remaining dependency: Phase 2 is unstarted. No scope deviation; Scott authorized the single-Codex per-phase review workflow with a comprehensive audit after all phases. | — | n/a | Completed |
| 2 | Settings extraction (group A subset) → own module | Phase 1 | Negligible | Not yet |
| 3 | Composer geometry characterization (test-only) — full scope of Phase 4's move: sizing, char-cap truncation, placeholder visibility, scrollbar-policy transitions, the alignment-callback interaction, **surface-layout hook retry/idempotence/immediate reapply/layout-event behavior, and line/content/window-size fallbacks** | — | n/a | Not yet |
| 4 | Composer geometry/character-cap extraction *only* — explicit interface for `_placeholder` injection, `_composer_truncating`/`_composer_layout_hooked` ownership, the alignment callback, and **narrow surface/height/default-size providers**; explicitly rewires the initial height application plus buffer `changed`/`insert-text` and window `realize`/`map` connections | Phase 3 | Low | Not yet |
| 5 | Export characterization (test-only) — both formats, format normalization/fallback, basename/title fallback, missing-conversation no-op, dialog cancellation/non-cancellation errors, `None` file/missing-path no-ops, successful UTF-8 write, and write-failure logging/dialog behavior | — | n/a | Not yet |
| 6 | Export extraction via an **injected title provider** — `_conversation_display_title` stays conversation-owned (shared with delete-confirm), export takes a `title_provider` callback instead of owning or reaching back for it (**this callback gets re-bound and integration-tested in Phase 22**) plus its required store/transient-parent dependencies; `ChatSidebar.export_conversation` remains an intentional thin delegator so the two window actions and two popover callbacks keep one stable entrypoint | Phase 5 | Low-medium | Not yet |
| 7 | Health/probe characterization (test-only) — **all of group I, branch by branch**: `_refresh_models`' loading no-op; `_apply_health`; current no-generation-guard probe ordering and every healthy/no-model/unavailable/error transition; `_on_health_action`'s three branches; `_preferred_model` store priority/exception fallback; and `_select_model_name`/`_on_model_selected` exact/soft/no-match, placeholder/error, same-model, retry, warm/no-warm, and load-in-progress paths | — | n/a | Not yet |
| 8 | Health/probe extraction (group I), **excluding** `_set_load_controls_sensitive` and **not claiming ownership of model-session state** — owns `_health`, `_suppress_model_select`, `_health_action_id`, and `_health_action_model`; its explicit narrow contract supplies nullable current-model get/set, loading/failed reads, failed-state write, begin-load, messages-empty, active-conversation model-preference, status, overlay-hide, shared-sensitivity, send-sensitivity, and input-sensitivity callbacks/providers, plus the client/model-selector/refresh/health-presentation dependencies. Phase 10 rebinds model-session callbacks; Phase 22 later rebinds message/conversation providers | Phase 7 | Medium | Not yet |
| 9 | Model-load characterization (test-only) — empty-model/streaming no-ops; stale status/chunk/finish ordering; cancellation/generation replacement; one-pulse-only start, stop, hidden-overlay termination, and determinate/indeterminate transitions; NDJSON mapping; success/failure completion UI and sensitivity ordering; last-model/conversation-model persistence ordering and failure continuation; repeated-load greeting dedup; and **the exact clear/successful-new/switch reset placement, including no reset for the already-empty `new_chat` branch** | — | n/a | Not yet |
| 10 | Model-load extraction (group J), **excluding** `_set_load_controls_sensitive` and `_show_ephemeral_greeting`, and becoming sole canonical owner of `_model`/`_loading_model`/`_load_failed`/`_load_generation`, loader-private `_stop_load`/`_load_pulse_id`/`_load_indeterminate`, and `_greeted_models`. It migrates Phase 8's callbacks; exposes model-session queries/mutations plus `reset_greetings()`; receives an `ensure_conversation` provider for successful model-preference persistence, re-bound in Phase 22; **immediately rewires `clear_chat`/successful `new_chat`/`switch_conversation` to call that reset at their existing branch positions**; and installs read-only delegating compatibility properties for unmigrated `_model`/`_loading_model`/`_load_failed` readers until their inventoried Phase 18/20/22/24/26 migrations complete | Phase 8, Phase 9 | Medium | Not yet |
| 11 | Transcript reset/replay/removal characterization (test-only) — covers requested-native **and forced WebKit-constructor fallback**, including today's post-fallback `ensure_md_css()` behavior; exact empty/native-row transitions; replay role/content/ID fallback; and removal/reset behavior in both backends | — | n/a | Not yet |
| 12 | Transcript adapter foundation: after final backend selection, establishes the **single canonical transcript/native-state owner** (`_web` or native widget/scroller/box, `_native_rows`, empty/icon/title/subtitle state), reset/replay/removal, and the lowest-level row primitive needed before Phase 16. Retained window entrypoints become explicit delegators with inventoried removal phases; replay receives a message-ID provider re-bound in Phase 22; the retained theme callback uses the owner interface | Phase 11 | Medium-high | Not yet |
| 13 | Status-message and greeting characterization (test-only) — non-persisted CLI status-row create/update/done behavior and ephemeral greeting, both backends, using the Phase-12 state/row foundation | Phase 12 | n/a | Not yet |
| 14 | Transcript adapter seam: status messages and greeting — extends Phase 12's same owner; rewires `_post_status_message`/`_update_status_message`/`_show_ephemeral_greeting`'s transcript branching without moving those methods' business ownership, using the Phase-12 row primitive rather than window rendering | Phase 12, Phase 13 | Medium | Not yet |
| 15 | Streaming-update/finalization and native-intent characterization (test-only) — begin modes, opaque native-handle currentness/`_render_serial`, paced and leftover deltas, error/empty/success finalization, final action-row replacement, scrolling, and native copy/edit/action dispatch including dialog cancel/save; both backends | Phase 14 | n/a | Not yet |
| 16 | Transcript adapter completion: explicit opaque stream-handle protocol (`begin`/`is_current`/`delta`/`error`/`finalize`/final-row replacement), native action/edit rendering, and intent dispatch. Injects `on_intent`, `current_text`, transient-parent, and message-ID providers; Phase 22 rebinds text/ID providers and Phase 24 rebinds intent dispatch. Retains only inventoried window delegators needed by groups L/M until Phases 24/26 | Phases 12, 14, 15 | Medium-high (riskiest adapter slice) | Not yet |
| 17 | Sidebar/history-UI characterization (test-only) — all eight Phase-18 methods **plus their construction wiring**: `_sidebar_syncing` recursion guard, action/toggle and row-activation signals, initial idle rebuild/title callbacks, title guards/fallback/truncation, dirty/clean/empty/error rebuild branches, selection, activation, and popover dispatch | Phase 10 | n/a | Not yet |
| 18 | Sidebar/history-UI extraction (group E) — owns `_history_dirty`, `_sidebar_syncing`, and its injected widget references; rewires construction-time action/signal/idle callbacks; consumes Phase 10's loading interface immediately and window streaming/active-ID providers until Phases 26/22. `on_activate`/`on_delete` rebind in Phase 22; `on_export` remains Phase 6's stable delegator. Explicit `ChatSidebar` delegators cover retained callers: mark/rebuild through Phase 22 and title refresh through Phase 26, with removal gates recorded | Phases 10, 17 | Medium | Not yet |
| 19 | Composer-CLI-command characterization (test-only) — all eight Phase-20 methods plus `_send`'s two CLI-facing calls; command parsing and busy rejection; status non-persistence; progress formatting, duplicate suppression, same-phase replacement, 12-line cap, redundant-update suppression, clean EOF without explicit success, both exception families, and completion ordering (`status row → clear busy → refresh/restore status`) | — | n/a | Not yet |
| 20 | Composer-CLI-command extraction (group K) — owns `_ollama_cli_busy`; exposes `is_busy()`/`try_command()` and **immediately rewires `_send` to them**, leaving no invalid raw-attribute interval. Its contract injects client, transcript status surface, Phase-10 current-model query, status callback, narrow `on_cli_busy_changed`, Phase-8 `on_pull_succeeded`, scheduler/worker boundary, and message-ID provider re-bound in Phase 22 | Phases 8, 10, 14, 19 | Medium | Not yet |
| 21 | Conversation-lifecycle characterization (test-only) — covers every Phase-22 move not already protected elsewhere: new/clear/delete/confirm and switch pruning/failure ordering; `_ensure_conversation` reuse-vs-create; `_persist_message` ID forwarding, user-only dirty/title scheduling, assistant behavior, and failure continuation; sequential `_next_msg_id` counter/format; and exact `_history_restored` writes. Phase-9 greeting-reset tests remain authoritative and must continue passing; no duplicate concurrent-ID guarantee is invented | — | n/a | Not yet |
| 22 | Conversation-lifecycle extraction (group F) — **establishes the canonical in-memory active-conversation projection (conversation ID + messages *only*)** via a staged migration: `ConversationStore` stays canonical persisted storage; this phase owns the projection + a **getter-and-setter** compatibility facade (a getter alone can't support group L's whole-list reassignment call sites); **migrates every currently-known read-only `_messages` consumer**, including the transcript-adapter's `current_text()` accessor, Phase 8's `_preferred_model`, Phase 18's active-ID accessor, and Phase 6's title-provider callback, with an integration assertion that the rebound export provider sees the migrated projection; **rebinds Phase 10's `ensure_conversation`, the Phase-12 replay, Phase-16 native-rendering, and Phase-20 CLI message-ID providers**, plus the Phase-16 text provider; re-points Phase 18's `on_activate`/`on_delete` callbacks and retires its shorter-lived mark/rebuild delegators. Constructor restore is rewired directly, while intentional thin `ChatSidebar` lifecycle/persistence delegators preserve UI, test, and retained-controller entrypoints without duplicating state. It **preserves Phase 10's already-rewired `reset_greetings()` calls at their exact branch positions**, owns message-ID allocation, preserves `_history_restored`, and preserves Phase 21's persistence-failure asymmetry | Phase 12, Phase 21 | Medium-high | Not yet |
| 23 | Message-action characterization (test-only, group L, both transcript modes) — all eight Phase-24 methods, including lookup/API filtering/clipboard behavior; invalid-ID, busy/loading/model, role, and latest-assistant guards; delete/drop persistence failures and `keep_ui_id`; regenerate/edit/continue branch behavior; direct `_on_web_intent` routing; and completed regenerate/continue commits through `_commit_assistant_result` | Phase 11/15 (as template) | n/a | Not yet |
| 24 | Message-action extraction (group L, native-rendering **and message-ID allocation excluded** — both belong elsewhere per round 7) — **migrates onto Phase 22's interface**, rebinds Phase 16's `on_intent` provider and WebKit dispatch, immediately rewires group M's surviving `_api_messages`/`_find_message_index` calls to the controller interface, and retires transcript action/removal delegators that no longer have callers. Intentional thin `ChatSidebar` action delegators keep Phase-23 tests and stable dispatch entrypoints valid; the messages facade remains because group M still mutates it | Phase 16, Phase 22, Phase 23 | Medium-high | Not yet |
| 25 | Streaming characterization (test-only) — non-cancellation error paths mid-stream, **plus `_send` itself**: empty-input and busy guards; composer-command routing; unhealthy-reprobe and missing-model guards; buffer-clear placement; both-backend transcript insertion before in-memory append; ID forwarding; and the exact transcript → projection → persistence → composer-hint → stream-start sequence. These are new direct tests, not a re-run treated as coverage | — | n/a | Not yet |
| 26 | Streaming-engine extraction (group M), last — migrates onto the Phase-8 health, Phase-10 model-session, Phase-12/14/16 transcript, Phase-18 sidebar/title, Phase-20 CLI, Phase-22 message-state, and Phase-24 message-action interfaces. Rebinds Phase-22 cancel and Phase-24 start-stream providers; retains intentional thin `ChatSidebar` delegators for UI/test entrypoints (`_send`, `_start_assistant_stream`, `_request_stop`, `_invalidate_active_stream`); and leaves `_set_status` as a window presenter re-bound to engine/model/sidebar queries. A whole-file inventory then gates removal of raw transcript/sidebar/model-session compatibility and the Phase-22 messages facade; Phase-20 `is_busy()`/`try_command()` remain permanent | Phases 12-16, 22, 24, 25 (and in practice 8, 10, 18, 20, since `_send` calls into all of them) | High | Not yet |

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
| **Conversation lifecycle entrypoints and helpers** (`clear_chat`/`new_chat`/switch/delete/confirm/restore/ensure/persist) | Called from constructor and group-C actions/buttons; E activation/delete callbacks; J model-preference persistence; M send persistence; enforced tests call `switch_conversation`/`_persist_message` directly | **Phase 22** | Existing `ChatSidebar` methods until extraction | Phase 22 rewires constructor restore and rebinds E/J callbacks/providers; intentional thin `ChatSidebar` delegators preserve public/UI/test lifecycle and persistence entrypoints; Phase 26 consumes the owner directly while the stable delegators remain | N/A for intentional delegators; no duplicated mutable state | Phase 21 plus Phase 9 greeting/persistence, Phase 11 replay, and existing restore/stream tests |
| **Message-ID allocation** (`_next_msg_id`, `_msg_counter`) | Called from F (`_apply_restored_transcript`), K (`_post_status_message`), M (`_send`, `_start_assistant_stream`), native rendering (`_append_message`) — **never L** | **Phase 22** | Plain `ChatSidebar` method (`_next_msg_id`) unchanged until Phase 22; Phases 12/16/20 receive it as an injected provider rather than reaching back into the window | Phase 22 rebinds the replay/native-rendering/CLI providers from Phases 12/16/20; Phase 26's streaming engine consumes the owner directly | N/A (thin delegator retained, not a raw-attribute facade) | Phase 21 covers sequential counter progression and exact `{prefix}-{counter}-{uuid suffix}` format; no unsupported concurrent-allocation guarantee |
| **Message-action entrypoints and helpers** (`_find_message_index`, `_api_messages`, copy/delete/drop/regenerate/edit/continue) | Called by WebKit intent dispatch, Phase-16 native intent/action rendering, and M (`_start_assistant_stream` calls `_api_messages`; `_commit_assistant_result` calls `_find_message_index`); Phase-23 tests call the window action methods | **Phase 24** | Existing `ChatSidebar` methods until extraction | Phase 24 rebinds WebKit/native dispatch and immediately rewires M's two helper calls; intentional thin window action delegators remain for stable dispatch/tests | N/A for intentional delegators | Phase 23 covers all eight methods, guards, persistence/UI branches, routing, and completed replace/continue |
| **Model session** (`_model`, `_loading_model`, `_load_failed`, `_load_generation`; loader-private `_stop_load`, `_load_pulse_id`, `_load_indeterminate`) | I writes `_model`/`_load_failed` and reads `_model`/`_loading_model`/`_load_failed`; J writes all four canonical fields and exclusively owns the three loader-private fields. Direct readers also remain in E (`_refresh_chat_title`), F (clear/new/switch/ensure/restore), L (message-action guards), K (CLI sensitivity/status), M (send/start/finish), N (`_set_status`), and retained `_set_load_controls_sensitive` | **Phase 10** | Phase 8 uses callbacks into `ChatSidebar` until Phase 10 migrates them. At cutover, Phase 10 supplies read-only delegating `ChatSidebar` compatibility properties for `_model`/`_loading_model`/`_load_failed`; `_load_generation` and the loader-private fields stay internal because no outside consumer needs them | Phase 18 sidebar/title; Phase 20 CLI; Phase 22 lifecycle/ensure/restore; Phase 24 message actions; Phase 26 send/stream/status. Phase 26 also rewires any retained `_set_load_controls_sensitive` or other window readers found by the required whole-file inventory | **Phase 26**, only after the whole-file inventory proves no raw compatibility-property consumers remain | Phase 9: no-op guards, generation/stale callbacks, cancellation, pulse/progress lifecycle, completion UI, sensitivity and persistence ordering |
| **Greeting deduplication** (`_greeted_models`) | Cleared by F (`clear_chat`, successful `new_chat`, `switch_conversation`); read + mutated only by J (`_on_model_load_finished`) — I never touches it | **Phase 10** | Plain attribute until Phase 10 | **Phase 10 immediately rewires all three F call sites to `reset_greetings()` at their existing branch positions**; Phase 22 preserves those calls when it later extracts F | N/A (no invalid interim facade or second owner) | Phase 9: repeated-load dedup plus clear/successful-new/switch resets and the already-empty-new no-reset branch |
| **Health/probe state** (`_health`, `_suppress_model_select`, `_health_action_id`, `_health_action_model`) | Written/read within I except `_health`, which M reads to decide whether `_send` re-probes | **Phase 8** | N/A — I owns outright once extracted; model-session and message/conversation state are supplied through the Phase-8 callback/provider contract | Phase 10 rebinds model-session callbacks; Phase 22 rebinds message/conversation providers; Phase 26 consumes health for `_send` | N/A | Phase 7 branch-level coverage for all seven I methods; Phase 25 covers `_send`'s reprobe branch |
| **Streaming state and entrypoints** (`_streaming`, `_stream_generation`, `_active_stream_cancel`; send/start/stop/invalidate) | M owns state/methods; F/L/E/J/K/N and sensitivity policy read state. Group-C buttons, retained `_on_input_key`, F/L callbacks, and enforced tests call M entrypoints directly | **Phase 26** (last) | Plain attributes/methods until Phase 26; previously extracted F/L/E/J/K readers use callbacks into `ChatSidebar` | Phase 26 rebinds every reader/provider to engine queries and F/L callbacks to engine commands. Intentional thin `ChatSidebar` delegators for `_send`, `_start_assistant_stream`, `_request_stop`, and `_invalidate_active_stream` preserve UI/test entrypoints without owning state | N/A for intentional delegators; raw state compatibility ends in Phase 26 after whole-file inventory | Existing generation-lifecycle tests plus Phase 25's direct `_send` and error coverage |
| **CLI busy state and entrypoint** (`_ollama_cli_busy`, `_try_composer_command`) | K owns the command methods and busy writes/reads; M's `_send` reads the raw busy attribute and calls `_try_composer_command` directly | **Phase 20** | Dynamically-created plain attribute/methods until Phase 20 | **Phase 20 immediately rewires `_send` to controller `is_busy()`/`try_command()` calls**; Phase 26 preserves those interface calls when it extracts M | N/A (no interim facade or duplicate flag) | Phase 19 covers the two `_send` integrations plus the full CLI state machine |
| **Sidebar presentation state and inbound calls** (`_history_dirty`, `_sidebar_syncing`, sidebar/history/title widget references) | Group C initializes state/widgets and connects actions/signals/idles; E reads/writes both flags and owns all eight methods; F calls mark/rebuild/title through Phase 22; N's `_set_status` calls title refresh through Phase 26 | **Phase 18** | Plain attributes/methods until Phase 18 | Phase 18 rewires construction callbacks and retains explicit window delegators: mark/rebuild through Phase 22, title refresh through Phase 26; `on_activate`/`on_delete` rebind in Phase 22, while `on_export` stays on Phase 6's stable delegator; streaming/active-ID providers rebind in Phases 26/22 | **Phase 26**, after the last title-refresh caller migrates; shorter-lived mark/rebuild delegators retire in Phase 22 | Phase 17 covers both method behavior and construction/inbound wiring |
| **Transcript presentation/state** (`_transcript_mode`, `_web`; native widget/scroller/box, `_native_rows`, empty/icon/title/subtitle state; status/greeting/stream rendering) | Touched by C, F, K, L, M and native rendering; `_native_remove_message`/`_append_message` have callers surviving until Phases 24/26 | **Phase 12 establishes the single state owner; Phases 14/16 extend its API** | Phase 12 installs explicit `ChatSidebar` method delegators for signatures retained callers still use; no raw mutable-state property or duplicate container is exposed | Phase 14 moves status/greeting branching onto the owner; Phase 16 adds opaque streaming/native-intent APIs; Phases 20/22/24/26 migrate K/F/L/M callers and Phase 22 rebinds message-ID/text providers | **Phase 26**, only after a whole-file inventory proves no retained transcript delegator/raw-state consumer remains | Phase 11 covers selection/fallback/reset/replay/removal; Phase 13 status/greeting; Phase 15 opaque stream identity/finalization/native intents |
| **Sensitivity policy** (`_set_load_controls_sensitive`, composer/nav/sidebar enablement) | **Current callers are exclusively I/J** (four call sites): I's `_refresh_models` (`window.py:2417`) and `_on_ollama_probe` (`2468`); J's `_show_load_overlay` (`2618`) and `_hide_load_overlay` (`2651`). **K does not call it today** — corrected: earlier revisions listed K in this "current" column, but K's Phase-20 narrow `on_cli_busy_changed` callback is *proposed* design, not current state, and per the CLI-busy row it deliberately does **not** call `_set_load_controls_sensitive` (which touches far more widgets than K's send-button-only behavior) | **Deliberately unresolved** — §5 risk 3, a decision for Scott | N/A | N/A until Scott authorizes a consolidation phase | N/A | None directly; exercised only incidentally through Phases 7-10/19-20's tests — flagged as a known gap, out of scope for these 26 phases |
| **Status/title presentation** (`_conversation_display_title`, `_refresh_chat_title`, `_set_status`) | `_conversation_display_title` read by export (Phase 6) and delete-confirm (Phase 22); `_refresh_chat_title` (Phase 18) reads model/streaming/store/active-ID state; retained `_set_status` is called by I/J/K/M and falls back to title refresh | `_conversation_display_title` → **Phase 22**; `_refresh_chat_title` → **Phase 18**; `_set_status` → **retained `ChatSidebar` presenter** | Export's title provider stays bound to the window until Phase 22; Phase 18 retains a title-refresh delegator through Phase 26; extracted controllers receive the stable status callback | Phase 22 rebinds export/active-ID; Phase 26 rebinds `_set_status` to engine/model/sidebar queries and removes the now-unused title-refresh compatibility delegator | `_refresh_chat_title` delegator → **Phase 26**; `_set_status` remains intentional | Phase 5 export fallback; Phase 17 title/status behavior; Phase 22 export-provider integration; Phase 25 streaming status transitions |

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
  rather than re-derived from prose each round.
- 2026-07-23 (round 8) — Browser GPT reviewed immutable published commit
  `6040d39` and reported seven candidate findings for Phases 1-10. Codex
  then verified each candidate against the synchronized local checkout,
  current source, tests, phase text, and ownership matrix. Six structural
  findings were confirmed: Phase 10's invalid greeting-ownership
  interval; the incomplete model-session consumer/facade lifecycle;
  missing loader-private ownership and Phase-9 behaviors; Phase 8's
  incomplete callback/provider and internal-state contract; export's
  missing async/no-op coverage and delegator/provider lifecycle; and
  composer's missing geometry providers and build-time signal migration.
  The settings candidate identified useful concrete assertions but was
  not a structural defect because Phase 1 already requires every moved
  behavior and Phase 2 already requires re-export compatibility.
  **Consensus so far covers the findings from all eight rounds and the
  general revision direction; it does not yet cover the precise 26-phase
  table as final** — that table is the current best draft and remains
  open to a further review round. No phase is approved for implementation
  until Scott says so, independent of whether the research documents
  reach a stable state.
- 2026-07-23 (round 9) — Browser GPT directly audited the published
  repository at immutable commit `4473906` for Phases 11-20 and reported
  eight candidates. Codex verified all eight against the synchronized
  checkout, source, tests, table, and matrix. The transcript split lacked
  a dependency-closed pre-Phase-16 row primitive, a single staged state
  owner, inbound method-delegator lifecycles, an opaque native stream
  identity protocol, and forced WebKit-construction-fallback coverage.
  Phase 18 omitted `_sidebar_syncing`, construction signal/action/idle
  rewiring, retained inbound callers, and the stable-export exception to
  its Phase-22 rebind wording. Phase 20 took over CLI state and methods
  while `_send` still used raw window surfaces until Phase 26, and its
  controller/test contract omitted model-session, message-ID, status,
  scheduling, and pull-loop behavior. One proposed remedy was narrowed:
  Phase 10 is a hard Phase-18 interface prerequisite, but Phase 6 need
  not be if `on_export` remains on its intentional stable delegator.
  **Consensus now covers the findings from all nine rounds and the
  revision direction, not final approval of any phase.** No implementation
  is authorized.
- 2026-07-23 (round 10) — A remote Grok pass reviewed published commit
  `607b818` for Phases 21-26. Local Codex verification rejected its
  proposed duplicate pruning/greeting-reset coverage and concurrent-ID
  guarantee: pruning was already in detailed Phase 21, greeting placement
  was already protected by Phase 9 and preserved by Phases 10/22, and the
  current allocator has no concurrent-call contract. The local audit then
  found six material gaps the remote pass missed: Phase 21 did not fully
  characterize `_ensure_conversation`/`_persist_message`; Phases 22, 24,
  and 26 omitted retained caller/delegator lifecycles; Phase 23 did not
  enumerate the branches of all eight moved methods; and Phase 25 omitted
  buffer/transcript placement in `_send`'s success ordering. Those
  corrections were folded into the table, matrix, and audit without
  changing the 26-phase order. **Consensus covers all ten locally verified
  rounds and the revision direction; no phase is approved for
  implementation.**

## Successful phase reporting

This is a living plan, not an append-only progress log. An unstarted phase
remains a proposal in the phase table. After a phase is merged and verified
on a clean, synchronized `main`, replace that phase's existing proposal row
in place with a concise factual completion report.

Each successful completion report records:

- completed status, PR link, and merge SHA;
- actual scope and files changed;
- exact tests and CI checks run, with results;
- the behavior or guarantee preserved by the phase;
- any remaining compatibility interface or downstream dependency; and
- any approved deviation from the proposal.

Replace obsolete predictions and instructions for the completed phase; do
not append a second history entry below the table and do not create a
separate status, handoff, or progress-log file. Git history preserves the
superseded proposal. In the same update, correct any document-wide status,
approval, sequencing, dependency, or ownership-matrix claim made stale by
the completed phase; these are current-state corrections, not appended
history. Failed, incomplete, or merely attempted work is not reported as
successful progress: its phase remains uncompleted until the required
result and verification exist.
