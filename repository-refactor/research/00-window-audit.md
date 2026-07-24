# 00 — window.py / ChatSidebar Audit

Status: research evidence. Does not authorize any code change by itself —
see `../REFACTOR_PLAN.md` for the proposals derived from this audit and
Scott's decisions on them.

Scope: `window.py` as of commit `d12bf2e` (main, recovery closed
2026-07-23). File is 3,753 lines; the module holds a handful of top-level
helpers/constants (lines 1-494) and a single class, `ChatSidebar`
(`Adw.ApplicationWindow` subclass, lines 495-3742, 99 methods). The class
body ends at line 3742; lines 3743-3753 are the module-level helper
`_fmt_bytes` (`def` at 3745, column 0), which is listed under group A
below and is *not* a `ChatSidebar` method.

Method used: read the file in full, section by section, cross-referenced
against the 15-script test suite (`scripts/test_*.py`) and the sibling
modules `ChatSidebar` already depends on (`conversation_store.py`,
`ollama_client.py`, `ollama_health.py`, `transcript_view.py`,
`message_widgets.py`). Every claim below is anchored to a line number or a
file; nothing here is inferred from naming alone.

**Revision note (round 1):** this document was independently reviewed
(Codex/ChatGPT) against the same source tree. Every finding in that
review was checked directly against the code or by re-running the test
suite and confirmed correct; that revision folded in corrections to
attribute/mutation counts, the `_on_ollama_probe` generation-guard gap,
the composer-boundary scope, `_conversation_display_title` ownership, the
native-mode verification claim, stale `§` cross-references, and the
phase-size/granularity of §7.

**Revision note (round 2):** a second review pass found the round-1
phase plan still had problems: a monolithic characterization phase
(recreating the exact defect round 1 fixed elsewhere), an incompletely
specified composer extraction boundary (missed `_placeholder`,
`_composer_truncating`, `_composer_layout_hooked`, and the
`_sync_composer_action_valign` callback), two methods misassigned to the
wrong owner (`_set_load_controls_sensitive`, `_show_ephemeral_greeting`),
three native-transcript methods miscategorized as mode-agnostic "message
actions" when they're actually the native transcript backend, an
unsupported dependency claim (sidebar/history UI does not touch
transcript rendering at all), stale top-level helper line numbers, and
loose wording that treated "add a behavior change in the same PR as the
extraction" as a live option rather than something the ground rules
already forbid. Every one of those was verified directly against the
code (see §2, §4.3, §7 below) and folded in here. Consensus so far is on
the corrected findings and the general revision direction (just-in-time
characterization, no monolithic test phases, preserve-behavior-first);
the phase table itself is still being negotiated and is not yet a
locked agreement — see `../REFACTOR_PLAN.md` decisions log.

**Revision note (round 3):** a third review pass found the round-2 phase
table still inconsistent and incomplete: (a) it stated a "standalone test
phase before extraction" principle but Phases 1-5 didn't follow it while
later phases did; (b) four gaps already named in §6.2 — conversation-
lifecycle UI flows (`new_chat`/`clear_chat`/`delete_conversation`/
`_confirm_delete_conversation`), `_make_chat_actions_popover`,
`_on_web_intent` dispatch, and streaming's non-cancellation error path —
were documented as gaps but never turned into actual phases; (c) `_messages`
ownership (§5 risk 4) was flagged as needing an explicit decision but no
phase was assigned to make it; (d) moving the native action-bar methods
into the transcript adapter (round 2) would, if done as literally
described, drag message-action business logic and direct `_messages`
reads into what was supposed to be a pure-rendering seam, since
`_native_action_bar`/`_native_edit_user` call group-L methods and read
`_messages` directly today (verified); and (e) two more extraction seams
(export's dependency on `_conversation_display_title`, the CLI-busy
flag's direct `send_btn` sensitivity writes) needed the same
narrow-interface treatment already applied elsewhere. Every finding was
verified directly against the code before being folded in. This produced
the round-3 structure: 22 phases in 11 test/extract pairs, with no
bundled exceptions, `_messages` ownership explicitly assigned to Phase
18, and an explicit intent-dispatch interface required for Phase 12.

**Revision note (round 4):** a fourth review pass found round 3's
resolution of `_messages` ownership (Phase 18) described a destination
without a migration path — Phase 18 runs before groups L/M are extracted,
so it cannot make itself the sole owner without either reaching into
not-yet-extracted phases (scope creep) or providing a compatibility seam;
Phase 16's "report through the window's sensitivity policy" wording could
have meant literally calling `_set_load_controls_sensitive`, which
touches far more widgets than `_set_composer_cmd_busy` does today and
would have been an accidental behavior change; Phase 14 needed the same
injected-callback treatment already applied to Phases 8/10/16 but instead
still said "plain method calls... valid regardless of order," when
`_on_history_row_activated`/`_make_chat_actions_popover` call
`switch_conversation`/`export_conversation`/`_confirm_delete_conversation`
directly; Phases 3 and 9's characterization scope was narrower than what
their paired extraction phases (4, 10) actually move; Phase 19 lacked any
requirement to exercise a *completed* (not cancelled) regenerate/continue
through to `_commit_assistant_result`'s replace/continue branches
(confirmed: `test_generation_lifecycle.py` has zero references to
`"replace"`/`"continue"` mode); and the dependency column was ambiguous
about whether it was meant to be exhaustive. Every finding was verified
directly against the code (including re-reading `_run_ollama_pull`'s
completion callback and `_on_history_row_activated`'s body) before being
folded in: Phase 18 now specifies a four-part staged migration
(`ConversationStore` stays canonical persisted storage; Phase 18 owns an
in-memory projection; a temporary compatibility facade covers
not-yet-migrated callers; Phases 20 and 22 migrate onto the new interface,
with Phase 22 removing the facade); Phase 16 now specifies a narrow
`on_cli_busy_changed` callback that reproduces exactly today's
send-button-only behavior, plus a separate `on_pull_succeeded` hook for
the model-refresh call; Phase 14 now specifies injected `on_activate`/
`on_export`/`on_delete` callbacks; Phases 3 and 9 now list the full scope
of what Phases 4 and 10 move; Phase 19 now requires completed
replace/continue commit coverage; and the dependency column has an
explicit note that it lists ordering/interface prerequisites, not every
call-target.

**Revision note (round 5):** a fifth review pass found three more
problems. First, model-state ownership overlapped across three phases:
`self._model`/`self._load_failed` are written by both Phase 8's methods
(`_select_model_name`, `_on_model_selected`, `_on_ollama_probe`) and Phase
10's (`_on_model_load_finished`), while Phase 18's conversation projection
was described as also owning the active conversation's "model" —
verified all three claims directly against the code. Second, round 4's
claim that Phase 22 could cleanly remove the `_messages` compatibility
facade because "nothing will be left reaching for a raw `self._messages`"
was false: read-only consumers exist in methods belonging to *earlier*
phases (Phase 4's `_composer_hint_should_show`, Phase 8's
`_select_model_name`/`_on_model_selected`/`_on_ollama_probe`/
`_on_health_action`, Phase 10's `_on_model_load_finished`/
`_show_ephemeral_greeting`, and Phase 18's own `clear_chat`/
`_active_chat_is_empty`/`new_chat`) — confirmed by direct search; the
same pattern applies to `_health`/`_loading_model`/`_load_failed`/
`_model`/`_ollama_cli_busy`, which `_send` (Phase 22) reads directly.
Third, `REFACTOR_PLAN.md`'s intro overstated the verification history,
claiming the 15-script suite was re-run "each time" across all four
rounds, when in fact it was run once (round 1) to establish the baseline
and rounds 2-4 were documentation-only revisions with no application code
to re-verify. All three findings were verified directly against the code
before being folded in: Phase 8 no longer claims ownership of model
state and instead reports via callbacks into whatever currently owns it;
Phase 10 becomes the sole canonical owner of model-session state
(`_model`/`_loading_model`/`_load_failed`/`_load_generation`) and
explicitly migrates Phase 8's already-extracted callback wiring onto its
new interface; Phase 18 now owns conversation ID and messages only (not
"model"); a **general migration invariant** now governs every staged
migration in this plan (read-only queries or delegating properties for
unmigrated consumers, no duplicated mutable state, facade removal only
after a whole-file direct-reference inventory finds zero remaining
consumers — mutating or read-only); Phase 22's facade-removal claim is
corrected to distinguish the mutation facade (which it can retire) from
full raw-reference removal (which requires migrating the read-only
consumers named above first, folded into this phase's own verification
scope); and `REFACTOR_PLAN.md`'s intro is corrected to accurately describe
when the suite was actually run.

**Revision note (round 6):** a sixth review pass found five more
problems. First, Phase 11's characterization scope (four native
message-row methods) doesn't match Phase 12's actual breadth (a
`TranscriptSink` contract spanning reset/empty-state, replay, removal,
status-message create/update, greeting, and streaming update/
finalization, 12+ call sites) — confirmed by re-reading Phase 12's own
description against Phase 11's. Second, `_greeted_models` was
misattributed in §3 as "written by groups I/J"; verified it's actually
cleared by three group-F methods and read/mutated by exactly one group-J
method, with group I never touching it — a two-owner overlap the plan
never resolved. Third, Phases 13/14 were under-specified: Phase 13 only
added popover coverage while Phase 14 moves eight methods, three of which
(`_refresh_chat_title`, `_select_active_history_row`,
`_on_history_row_activated`) and the `_history_dirty` short-circuit have
no test coverage at all (confirmed: `test_sidebar_interactions.py` only
*sets* `_history_dirty`, never exercises the short-circuit); and Phase
14's three presenter callbacks don't cover `_refresh_chat_title`'s direct
reads of `_loading_model`/`_streaming`/`ConversationStore`, or
`_history_dirty`'s ownership (verified every write site is group F, not
group E). Fourth, Phase 18's compatibility facade was described as a
read-through only, but group L's call sites include whole-list
*reassignment* (`self._messages = self._messages[:idx]`,
`window.py:2212,2239,2287`), which a getter-only property cannot support
— confirmed directly. Fifth, round 5's own reader inventory misattributed
two citations: `_composer_hint_should_show` was cited as "Phase 4" and
`_show_ephemeral_greeting` as "Phase 10," but both phases' own text
explicitly *excludes* these methods — they're retained on `ChatSidebar`,
not living inside those phases' extracted objects, which changes who can
fix them and when. Every finding was verified directly against the code
(including re-reading Phase 4's and Phase 10's own exclusion text, every
`_greeted_models` and `_history_dirty` read/write site, and the exact L
call sites doing whole-list reassignment) before being folded in: Phase
11 now covers the full adapter contract (with an explicit note that Scott
may split it into sub-phases at implementation time given its size);
Phase 10 becomes `_greeted_models`' owner too, exposing `reset_greetings()`
for Phase 18 to call; Phase 13 now covers all eight Phase-14 methods, not
just the popover; Phase 14 now specifies status accessors and explicit
`_history_dirty` ownership beyond the three presenter callbacks; Phase
18's facade is now a getter-*and-setter* property; and Phase 18 (not
Phase 22) now migrates every currently-known read-only consumer at the
point it introduces the projection, since that work is either
`ChatSidebar`'s own retained code or the callback wiring `ChatSidebar`
supplies to already-extracted objects — never a reach into another
phase's controller internals — which in turn makes Phase 22's original
facade-removal claim (now corrected) actually true. Consensus remains on
findings and direction; the phase table is on its sixth revision and, per
the working rules, remains a draft until it survives a review round with
no further findings — see `../REFACTOR_PLAN.md` decisions log.

**Revision note (round 7):** a seventh review pass found six more
problems, the largest so far. First, the transcript-adapter phase (old
Phase 12) was itself oversized — confirmed by direct measurement: 13
methods, ~705 method-lines, including the 254-line
`_start_assistant_stream` — even though its characterization phase (old
11) had already identified three coherent slices, only the *PR-packaging*
was ever offered as splittable, not the phase structure itself. Second,
several characterization phases still didn't protect their paired
extraction: the health/probe characterization named only `_apply_health`/
probe-ordering while the extraction moves `_on_health_action`'s three
branches and `_preferred_model`, both completely untested; the CLI
characterization named three of the eight methods the extraction moves;
and the streaming characterization covered only mid-stream errors while
`_send` itself has zero coverage — confirmed via the test's own docstring
("mirror what `_send()` does, minus composer/health/model UI guards",
`scripts/test_generation_lifecycle.py:148`). Third, the conversation-
lifecycle characterization was missing a specific, real asymmetry:
`switch_conversation` continues past a `set_active` failure while
`delete_conversation` aborts past a store failure — a naive projection
could accidentally normalize this. Fourth, `_next_msg_id`/`_msg_counter`
were misassigned to the message-action phase; verified their real callers
span conversation-lifecycle, CLI, streaming, and native rendering —
never message actions at all. Fifth, the sidebar-extraction phase
contained two factual errors: it described `is_loading_model` as "still
window-owned" when the model-load-extraction phase (which precedes it)
had already landed and owned that state; and it attributed every
`_history_dirty` write to group F when the actual assignment sites are in
group C/E setup and `_mark_history_dirty` itself, with group F only
calling that method. Sixth, the conversation-lifecycle phase's own
reader-migration list (added in round 6) was still missing four
consumers: the transcript-adapter's `current_text()` accessor, the
health-probe phase's `_preferred_model`, the sidebar phase's active-ID
accessor, and the export phase's title-provider callback — plus the
sidebar phase's activate/delete presenter callbacks, whose *target*
methods move in this very phase and need re-pointing. Every finding was
verified directly against the code (including measuring every method's
line count, re-reading `test_generation_lifecycle.py`'s own docstring,
confirming `switch_conversation`/`delete_conversation`'s exact
except-block behavior, and tracing every `_next_msg_id` call site) before
being folded in. Given how many rounds had now found cross-phase
attribution errors that prose revisions kept re-introducing, this round
also adds a structured **ownership/migration matrix** to
`REFACTOR_PLAN.md` — one row per shared capability, columns for current
writers/readers, canonical owner, pre-owner compatibility interface,
later consumers requiring rewiring, facade-removal phase, and
characterization coverage — specifically so these relationships can be
checked mechanically rather than re-derived from scattered prose each
round. The transcript-adapter phase split into three test/extract pairs,
the affected characterization phases were widened, message-ID allocation
was reassigned, the sidebar phase's two errors were corrected, and the
conversation-lifecycle phase's reader-migration list was completed —
landing on **26 phases in 13 test/extract pairs**. Consensus remains on
findings and direction; the phase table is on its seventh revision and,
per the working rules, remains a draft until it survives a review round
with no further findings — see `../REFACTOR_PLAN.md` decisions log and
its ownership/migration matrix.

**Revision note (round 8):** browser GPT independently reviewed immutable
published commit `6040d39` and produced seven candidate findings for
Phases 1-10. It could inspect the published GitHub tree but not execute
local Git, hashes, the manifest check, or tests; it disclosed those limits.
Codex then verified every candidate against the clean synchronized local
checkout, `window.py`, the test bodies, this audit, and the active plan.
Six structural findings were confirmed: (1) Phase 10's ownership of
`_greeted_models` left its three group-F reset writers pointing at the old
attribute until Phase 22, an invalid twelve-phase interval; (2) the
model-session row omitted many live readers plus its compatibility
facade/removal lifecycle; (3) `_stop_load`, `_load_pulse_id`, and
`_load_indeterminate` were unassigned despite being private state of the
moved loader, and Phase 9 did not enumerate their behavior; (4) Phase 8's
callback/provider contract and `_suppress_model_select` ownership were
incomplete; (5) export characterization omitted dialog/write/no-op
branches and Phase 6 did not settle caller/delegator lifetime; and (6)
composer extraction omitted window-geometry providers and its build-time
signal migration. The seventh candidate listed valid positive-path
settings assertions, but was reclassified as useful enumeration rather
than a structural defect: Phase 1 already requires every moved settings
behavior and Phase 2 already requires re-export compatibility. The six
confirmed corrections are folded into §7 and the active matrix; no phase
number or order changed. Consensus remains on findings and direction;
the phase table is on its eighth revision and remains a draft until it
survives a review round with no further findings.

**Revision note (round 9):** browser GPT directly audited the published
repository at immutable commit `4473906` for Phases 11-20 and reported
eight candidate findings. Codex verified all eight locally against
`window.py`, the test bodies/evidence, this audit, and the active matrix.
Confirmed: (1) Phase 12 replay/status needed a dependency-closed native
row primitive before Phase 16; (2) transcript/native mutable state had no
single staged owner; (3) moving `_native_remove_message`/later
`_append_message` lacked inbound delegator lifecycles; (4) Phase 16's
streaming surface omitted native `_render_serial` identity/currentness;
(5) forced WebKit-constructor fallback was uncharacterized and its
backend-selection point unspecified; (6) Phase 18 omitted
`_sidebar_syncing`, construction wiring, and retained inbound callers;
(7) Phase 20's ownership of CLI state/methods left `_send` on raw window
surfaces until Phase 26; and (8) Phases 19/20 omitted material
controller dependencies and pull-loop behavior. The suggested Phase-6
hard dependency for Phase 18 was narrowed: only Phase 10 is a hard
state-interface prerequisite; `on_export` remains bound to Phase 6's
stable delegator. The corrections are folded into §7 and the matrix
without changing the 26-phase order. The ninth revision remains a
proposal; no implementation is authorized.

---

## 1. What window.py currently is

`window.py` is the single orchestrator that wires together five already
well-separated collaborator modules:

| Module | Role | Public surface (already clean) |
|---|---|---|
| `conversation_store.py` | SQLite-backed conversation/message persistence | `ConversationStore` — `create_conversation`, `get_conversation`, `get_active_conversation`, `list_conversations`, `set_active`, `is_empty`, `prune_empty_conversations`, `delete_conversation`, `export_dict`, `export_markdown`, `set_model`, `append_message`, `list_messages`, `delete_message`, `update_message`, `get_message`, `clear_messages`, `ensure_active` |
| `ollama_client.py` | HTTP transport to Ollama | `OllamaClient` — `list_models`, `is_model_loaded`, `load_model` (generator), `chat_stream` (generator, `cancel_event`), `pull_model` (generator), `format_list_models`, `format_ps_models` |
| `ollama_health.py` | Error classification / health probing | `HealthState`, `HealthKind`, `classify_error`, `probe_ollama`, `checking_state` |
| `transcript_view.py` | WebKit-backed transcript widget | `WebTranscriptView` — `post(event)`, `reset(messages)`, intent callback |
| `message_widgets.py` | Native GTK transcript widgets | `MessageBody`, `CodeBlock`, markdown rendering |

`ChatSidebar` itself never got a comparable seam. It owns: the entire GTK
widget tree construction, composer sizing/behavior, the docked history
sidebar, conversation lifecycle (new/switch/delete/clear/restore),
export, a minimal settings dialog, Ollama health/model-load orchestration,
message actions (edit/delete/regenerate/continue), the send/streaming
pipeline, and — because the transcript can be either the WebKit view or a
native GTK box — a parallel "if webkit / else native" branch through
almost every transcript-touching method.

---

## 2. Responsibility map (99 methods, grouped)

Line numbers are `def` locations in `window.py`. Groups are ordered
roughly from "least entangled with the rest of the class" to "most
entangled," which is also the rough order used for the proposed
extraction sequence in §7.

### A. Module-level helpers (not methods, but part of the same seams)
`_read_settings` (56), `_write_settings` (67), `_load_last_model` (78),
`_save_last_model` (83), `_pick_startup_model` (94), `_transcript_mode`
(109), `_use_pointer_cursor` (117), `_is_ephemeral_greeting` (467),
`join_continue` (472), `continue_seed_for_stream` (487), `_fmt_bytes`
(3745, bottom of file). All pure or near-pure functions; several are
already imported directly by tests (`join_continue`,
`continue_seed_for_stream`, `_is_ephemeral_greeting` in
`test_message_actions.py`).

### B. Window lifecycle / chrome
`__init__` (496), `set_close_handler` (586), `_handle_close_request`
(589), `_on_key` (595), `_install_css` (601), `toggle` (1522),
`hide_to_tray` (1529), `toggle_maximize` (1533).

### C. UI construction (GTK widget-tree build-out)
`_build_ui` (610, ~400 lines — header bar, health banner, transcript
slot, composer, load overlay, all in one method), `_build_history_sidebar`
(1007), `_build_load_overlay` (1179), `_make_empty_brand_icon` (1452),
`_brand_icon_path` (1435), `_sync_empty_brand_icon` (1470),
`_show_empty_state` (1481), `_render_empty_transcript` (1629),
`_remove_empty_state` (3161).

### D. Composer geometry/behavior
`_hook_composer_surface_layout` (1239), `_composer_line_height_px`
(1250), `_composer_max_visible_lines` (1265), `_composer_content_height_px`
(1280), `_apply_composer_height` (1295), `_sync_composer_action_valign`
(1321), `_update_composer_char_counter` (1337),
`_composer_hint_should_show` (1355), `_sync_composer_hint` (1363),
`_on_composer_insert_text` (1392), `_on_buffer_changed` (1413),
`_on_input_key` (2384). The pure-geometry subset (`_hook_composer_surface_layout`
through `_update_composer_char_counter`, plus `_on_composer_insert_text`/
`_on_buffer_changed`) is *mostly* self-contained, but not as cleanly as
the initial draft claimed. Two more couplings, beyond the three below,
surface on close reading: `_apply_composer_height` (1295) itself calls
`self._sync_composer_action_valign(...)` directly at its end
(`window.py:1319`), and `_on_buffer_changed` (1413) both calls
`self._sync_composer_action_valign` (via `GLib.idle_add`, `window.py:1433`)
*and* reads/writes `self._placeholder` directly (`window.py:1427-1428`) —
a widget built in `_build_ui` (group C), not initialized in `__init__`.
Two more pieces of state are private to this subset and must move with
it or be re-homed deliberately: `self._composer_truncating` (guards
re-entrant buffer edits, read/written in `_on_composer_insert_text` and
`_on_buffer_changed`) and `self._composer_layout_hooked` (a
dynamically-created attribute — never listed in `__init__` — set via
`getattr(self, "_composer_layout_hooked", False)` in
`_hook_composer_surface_layout`, `window.py:1241,1247`). None of this
makes the geometry subset a bad extraction candidate — it's still the
lowest-risk group in the file — but the extracted object needs an
explicit interface for the alignment call (a constructor-injected
callback, since `_sync_composer_action_valign` itself stays window-owned
per the note below) and a constructor-injected `_placeholder` reference,
plus explicit ownership of `_composer_truncating`/`_composer_layout_hooked`
as its own instance state. See §7 Phases 3-4 for the corrected boundary.
**But the group as listed is not uniformly low-coupling** — three
members break that isolation: `_composer_hint_should_show` (1355) reads
`self._messages` directly; `_sync_composer_action_valign` (1321) mutates
`self.send_btn`/`self.stop_btn` alignment (owned by group M/streaming);
and `_on_input_key` (2384) calls `self._send()` (group M) on Enter. See
§7 Phases 3-4 for how this changes the proposed extraction boundary.

### E. Sidebar / conversation-list UI
`toggle_sidebar` (1100), `_on_sidebar_toggled` (1151),
`_mark_history_dirty` (1156), `_refresh_chat_title` (1159),
`_rebuild_history_list` (1637), `_select_active_history_row` (1725),
`_on_history_row_activated` (1735), `_make_chat_actions_popover` (1741).

### F. Conversation/history management (business logic over ConversationStore)
`clear_chat` (1539), `_active_chat_is_empty` (1565), `new_chat` (1576),
`switch_conversation` (1944), `delete_conversation` (1918),
`_confirm_delete_conversation` (1896), `_conversation_display_title`
(1798), `_ensure_conversation` (2075), `_restore_history` (2098),
`_apply_restored_transcript` (2160), `_persist_message` (2082),
`_next_msg_id` (2071).
**Placement note for `_next_msg_id`:** the round-7 correction under group L
established that it does *not* belong to message actions (its five call
sites span F/K/M/N, never L) and deferred its owner to "§7's
conversation-lifecycle phase" — but no group list was ever updated, leaving
it unplaced in the responsibility map. It is listed here because
`REFACTOR_PLAN.md`'s ownership/migration matrix assigns message-ID
allocation (`_next_msg_id` + `_msg_counter`) to **Phase 22**, the
conversation-lifecycle (group F) extraction. This is shared allocation
infrastructure called from F/K/M/N, not F-private logic: it stays a plain
`ChatSidebar` method until Phase 22, which then re-points the already
extracted callers (Phases 16/20/26) at the new owner.

### G. Export
`_safe_export_basename` (1815), `export_conversation` (1824).
`_conversation_display_title` (1798, listed under group F) is a *shared*
dependency of this group and of `_confirm_delete_conversation` (F) — it
is called from both `export_conversation`-adjacent code (`window.py:1816`)
and `_confirm_delete_conversation` (`window.py:1897`), and it reads
`self._conversation_id`/`self._messages` in its fallback path. It should
not move with export; see §7 Phases 5-6 (export) and Phase 22
(conversation lifecycle, where it likely ends up owned).

### H. Settings (window-level entry point only; the real state lives in group A)
`open_settings` (1115).

### I. Model health / probing / model-list wiring
`_refresh_models` (2411), `_on_ollama_probe` (2428), `_apply_health`
(2476), `_on_health_action` (2527), `_preferred_model` (2547),
`_select_model_name` (2012), `_on_model_selected` (2392),
`_set_load_controls_sensitive` (2557). **Ownership correction:**
`_set_load_controls_sensitive` is listed here because groups I and J both
call it, but its actual body (`window.py:2557-2581`) sets sensitivity on
`self.input`, `send_btn`, `model_combo`, `_refresh_btn`/`_refresh_action`,
`_clear_btn`, `_new_chat_btn`/`_sidebar_new_btn`/`_sidebar_btn`, and
`_history_list` — composer, nav, and sidebar widgets that belong to
groups C/D/E, not to health specifically. It is shared UI-enablement
policy called *by* health/loading, not owned *by* health. See §7 for how
this changes the Phase 8/10 extraction boundary.

### J. Model loading / warm-up overlay
`_show_load_overlay` (2585), `_start_load_pulse` (2620),
`_stop_load_pulse` (2634), `_hide_load_overlay` (2642),
`_update_load_progress` (2653), `_begin_model_load` (2685),
`_on_load_status` (2746), `_on_load_chunk` (2774),
`_on_model_load_finished` (2780), `_show_ephemeral_greeting` (2849).
**Ownership correction:** `_show_ephemeral_greeting` is listed here
because `_on_model_load_finished` (J) calls it on success, but it is
called just as often by group F (`clear_chat` `window.py:1561`, `new_chat`
`window.py:1590,1617`, `switch_conversation` `window.py:1995`), and its
body writes directly into the transcript (`self._web.post(...)` or
`chat_box` manipulation) — that's transcript/window presentation (groups
C/N), not model-loading logic. The model-load controller should call
*out* to a presentation callback (e.g. "model ready, no messages yet →
should I greet?"), not own this method itself. See §7 Phase 10.

### K. Composer-typed Ollama CLI commands (`ollama pull|list|ps`, HTTP not chat)
`_try_composer_command` (2920), `_composer_cmd_busy` (2947),
`_set_composer_cmd_busy` (2950), `_format_pull_progress` (2985, static),
`_run_ollama_pull` (3003), `_run_ollama_info` (3085),
`_post_status_message` (2901), `_update_status_message` (2962).

### L. Message actions (edit / delete / regenerate / continue)
`_find_message_index` (2185), `_api_messages`
(2191), `_clipboard_set` (2199), `_delete_message` (2204),
`_drop_messages_from` (2234), `_regenerate_message` (2255),
`_edit_resend_message` (2299), `_continue_message` (2340).
**Ownership correction (round 7):** `_next_msg_id` (2071) was originally
listed here by proximity/naming, but verified it's never actually called
from any of this group's methods — its five call sites are
`_apply_restored_transcript` (group F, `window.py:2177`),
`_post_status_message` (group K, `window.py:2903`), `_send` and
`_start_assistant_stream` (group M, `window.py:3143,3450`), and
`_append_message` (group N/native rendering, `window.py:3181`). See §7's
conversation-lifecycle phase for where this and `_msg_counter` actually
get assigned an owner.
**Ownership correction:** `_native_edit_user` (3360), `_native_action_bar`
(3251), and `_native_remove_message` (3401) were originally listed in
this group by naming ("message actions"), but they are not mode-agnostic
business logic — they *are* the native-GTK-backend implementation of
transcript rendering for a message row (building/tearing down the row
widget and its action-button strip), the direct counterpart to whatever
the WebKit side does in JS. They belong with the native transcript
renderer (group N / the Phase 12 transcript adapter's native
implementation), not with the mode-agnostic edit/delete/regenerate/
continue rules above — and per Phase 12, they must be reworked to emit
intents through an injected callback rather than calling group-L methods
or reading `_messages` directly, mirroring how the WebKit side already
works via `_on_web_intent`. See §7 Phase 12.

### M. Send / streaming pipeline (largest, most coupled group)
`_send` (3121), `_start_assistant_stream` (3420, ~250 lines),
`_commit_assistant_result` (3674), `_stream_finished` (3731),
`_request_stop` (2878), `_invalidate_active_stream` (2883),
`_scroll_to_end` (3409).

### N. Transcript rendering (native path) / status line
`_append_message` (3170), `_set_status` (2368), `_native_action_bar`
(3251), `_native_edit_user` (3360), `_native_remove_message` (3401).
The three `_native_*` methods are listed here explicitly: the round-7
ownership correction under group L reassigned them from L to N (they are
the native-GTK backend implementation of message-row rendering, not
mode-agnostic message-action logic), but earlier revisions recorded that
reassignment only in group L's prose and never added them to this list —
leaving them unplaced in the responsibility map itself. Per §7, they must
be reworked to emit intents through an injected callback rather than
calling group-L methods or reading `_messages` directly.

### O. Web-intent bridge (WebKit page → Python)
`_on_web_intent` (2048) — routes `copy_text`/`regenerate`/`continue`/
`delete_message`/`edit_resend` intents from `transcript_view.py` back
into group L.

---

## 3. State inventory (from `__init__`, lines 496-557)

59 instance attributes are assigned directly in `__init__`. The ones that
matter for extraction boundaries, grouped by who reads/writes them:

- **Conversation identity & transcript mirror**: `_conversation_id`,
  `_messages`, `_history_restored`, `_msg_counter`. `_messages` is
  read/written by groups F, L, M almost interchangeably — it's the single
  in-memory source of truth that every mutation path (send, regenerate,
  edit, continue, delete, restore, switch) keeps in sync with
  `ConversationStore` by hand. **Correction (round 7):** `_msg_counter`
  (backing `_next_msg_id`) is *not* an F/L/M-only concern — see the group
  L correction above, its real callers span F/K/M/N. `_history_restored`
  is written repeatedly by group F (`window.py:518,1613,1986,2132,2146,2158`)
  but confirmed **never read anywhere in the file** — it's write-only,
  dead in the sense that nothing currently branches on it. Whichever
  phase becomes its owner must preserve writing it (dropping it would be
  behavior-unrelated cleanup mixed into a structural extraction, against
  the ground rules), even though nothing consumes it today.
- **Streaming state**: `_streaming`, `_stream_generation`,
  `_active_stream_cancel`. Written by group M, but *read* by groups F
  (`switch_conversation`, `new_chat`, `delete_conversation` all check
  `_streaming` and call `_invalidate_active_stream`) and L (every message
  action guards on `_streaming`).
- **Model-session/load state**: `_model`, `_loading_model`,
  `_load_generation`, `_load_failed`, `_stop_load`, `_load_pulse_id`,
  `_load_indeterminate`. Groups I/J both write `_model` and
  `_load_failed`; J writes `_loading_model`/`_load_generation` and
  exclusively owns `_stop_load`/`_load_pulse_id`/`_load_indeterminate`.
  Direct readers span E/F/I/J/K/L/M/N plus the retained shared
  sensitivity method; §7 Phase 10 and the active plan's ownership matrix
  assign their staged migration.
- **`_greeted_models`** (correction, round 6): this was previously
  bundled into "model-load state" and misattributed as "written by groups
  I/J" — verified that's wrong. It's actually cleared by three group-F
  methods (`clear_chat` `window.py:1543`, `new_chat` `window.py:1611`,
  `switch_conversation` `window.py:1970`) and read + mutated by exactly
  one group-J method (`_on_model_load_finished`, `window.py:2837-2838`).
  Group I never touches it. This is a genuine two-owner overlap (F clears
  it on conversation transitions, J maintains dedup membership on load
  completion) — see §7 Phase 10's correction for the resolution.
- **Health**: `_health` (a `HealthState`), consumed by `_send` (group M)
  to decide whether to re-probe instead of sending.
- **Transcript mode**: `_transcript_mode` (`"webkit"` or `"native"`),
  `_web` (the `WebTranscriptView` or `None`), `chat_box`/`scroller`
  (native GTK containers), `_native_rows` (id → row widget, native only).
  Branched on in groups C, F, K, L, M — see §4.2.
  `_transcript_mode` is initialized from the module env var
  `CHICKENBUTT_TRANSCRIPT` at `__init__` (`window.py:509`), and **may still
  change once more during UI construction**: `_build_ui` reassigns it to
  `"native"` (`window.py:805`) in the `except` branch taken when
  `WebTranscriptView(...)` construction fails and the code falls back to the
  native GTK transcript. After `_build_ui` completes it is stable — nothing
  rewrites it during send/switch/stream. Any extraction that snapshots the
  mode at `__init__` time and passes it down would silently drop the
  native-fallback path.
- **Composer "busy" flags**: `_streaming`, `_loading_model`,
  `_load_failed`, `_ollama_cli_busy` (set via `_set_composer_cmd_busy`,
  group K). These four flags jointly gate `send_btn`/`input`/
  `model_combo`/`_refresh_btn`/`_clear_btn`/sidebar-nav sensitivity,
  computed in at least four different places (`_set_load_controls_sensitive`
  2557, `_set_composer_cmd_busy` 2950, inline in `_on_model_load_finished`
  2780-2813, inline in `_stream_finished` 3731). There is no single
  function that recomputes "is the composer allowed to send right now" —
  see §5, risk 3.
- **Widget references**: the remaining ~20 attributes are GTK widget
  handles set once in `_build_ui`/`_build_history_sidebar`/
  `_build_load_overlay` (group C) and read by nearly every other group.
  This is normal for a GTK window and not itself a defect, but it means
  any extracted controller needs those specific widget refs passed in
  explicitly rather than reaching back into `self`.

---

## 4. Dependency / data-flow tracing

### 4.1 Cross-group call graph (who calls into whom)

- **F → M**: `switch_conversation`, `new_chat`, `delete_conversation`
  all call `_invalidate_active_stream` (M) before mutating conversation
  state, so a stream that's mid-flight for the *old* conversation doesn't
  leak output into the *new* one.
- **F → N/C**: `switch_conversation`/`clear_chat`/`new_chat` all call
  `_apply_restored_transcript` or `_render_empty_transcript` (which
  dispatch to either `_web.reset()` or native `chat_box` rebuilding).
- **F → I**: `switch_conversation` restores the per-conversation model via
  `_select_model_name(conv.model, warm=True, ...)` — history and
  model-selection are coupled at this one call site (`window.py:2000`).
- **I → J**: `_on_ollama_probe` and `_on_model_selected` both call
  `_begin_model_load`; `_apply_health` is called from I, J, and M
  (streaming failures reclassify health via `classify_error`, `window.py:3543`).
- **J/M → E**: model-load completion and stream completion both call
  `_set_status`, which falls back to `_refresh_chat_title` (E) when not
  in a transient state (`window.py:2368-2382`).
- **L → M**: `_regenerate_message`, `_edit_resend_message`,
  `_continue_message` all end by calling `_start_assistant_stream` with a
  specific `mode` (`"new"`, `"replace"`, `"continue"`) — message actions
  and streaming are one feature split across two groups by necessity
  (streaming needs to know *why* it started).
- **O → L**: the WebKit intent bridge is a pure dispatch table into L's
  methods; this is already a clean seam.
- **K → N/M-adjacent**: `_run_ollama_pull`/`_run_ollama_info` post
  "status message" bubbles into the transcript using the same
  `_post_status_message`/`_update_status_message` machinery as streaming,
  but these are *not* persisted and *not* sent to the model — a separate,
  parallel "fake assistant message" concept that happens to share
  rendering code with M.

### 4.2 The transcript-mode branch (biggest structural coupling)

`if self._transcript_mode == "webkit" and self._web is not None: ... else: ...`
(or the inverse) appears, in some form, in at least 12 methods across
five groups: `_render_empty_transcript` (1629), `_apply_restored_transcript`
(2160), `_delete_message` (2204), `_drop_messages_from` (2234),
`_edit_resend_message` (2299), `_post_status_message` (2901),
`_update_status_message` (2962), `_show_ephemeral_greeting` (2849), and
three separate branch points inside `_start_assistant_stream`/its nested
`finalize_ui`/`flush_stream` closures (3420-3672). Every one of these
pairs must stay behaviorally identical between the WebKit JS-driven
transcript and the native GTK `MessageBody` transcript. This is the
single largest source of "if you extract this, you must extract both
halves in lockstep" risk in the file, and it is also the axis the test
suite is *least* symmetric about: WebKit-path behavior is well covered
(see §5), native-path behavior for message actions is not.

### 4.3 Generation counters as the concurrency invariant — and where they don't apply

`_stream_generation` and `_load_generation` prevent a background thread's
`GLib.idle_add` callback from mutating state after it's been superseded
(model switched, conversation switched, stream stopped, retried).
Streaming (group M) and model-loading (group J) callbacks capture their
generation number *by value* at the point the thread was started (e.g.
`gen = self._load_generation` at `window.py:2694`, `my_generation =
self._stream_generation` at `window.py:3432`) and compare it against the
live counter before acting.

**Correction from initial draft:** this protection is *not* uniform
across group I. `_on_ollama_probe` (`window.py:2428`), the callback for
`_refresh_models`'s background probe thread (`window.py:2411-2426`), has
**no generation guard at all** — it applies whatever `HealthState`/model
list it received unconditionally. `_refresh_models` has no in-flight
guard beyond `if self._loading_model: return False`; nothing stops two
overlapping probes (e.g. the refresh button/`Ctrl+R` pressed twice before
the first probe thread returns) from both landing in
`GLib.idle_add(self._on_ollama_probe, result)`, with whichever completes
last silently overwriting the other's UI state — a stale probe can win
over a fresher one. This is existing, pre-refactor behavior, not
something introduced by this audit's proposals; it's flagged here because
extracting group I is exactly the kind of change that could either
accidentally fix, accidentally worsen, or accidentally freeze this
behavior without anyone deciding to.

`test_generation_lifecycle.py` exercises the *stream*-generation races
end-to-end (switch mid-stream, stop vs. switch, stale-completion-can't-
reset-controls) — its own docstring scopes it to
`_start_assistant_stream`/`switch_conversation`/`_invalidate_active_stream`/
`_request_stop`, and it contains zero references to `_load_generation`,
`_begin_model_load`, or `_on_ollama_probe`. **Model-load generation
supersession and probe-ordering have no deterministic test in the
enforced suite at all** — the only place `_begin_model_load` is exercised
across repeated switches is `scripts/smoke_gui.py`, which needs a live
Ollama and is excluded from CI. A deterministic (fake-client, no network)
test for stale-load and stale-probe ordering should exist before group I
is extracted — see §7 Phases 8/10.

Any split of groups I/J/M into separate objects must keep the by-value-
capture pattern exactly where it already exists (J, M), and must make an
explicit, reviewed decision about whether group I should gain the same
protection or keep its current unguarded behavior — not drift into either
one as a side effect of the extraction.

---

## 5. Coupling risks worth naming explicitly

1. **Transcript-mode duplication** (§4.2) — the single biggest hazard.
   Any extraction touching groups C, F, K, L, M must either move both
   branches together or (better, but bigger) be preceded by introducing
   a small transcript adapter interface that the extracted code depends
   on instead of branching itself. See phase proposal in §7 (Phase 12).
2. **Generation counters as shared mutable invariants** (§4.3). Splitting
   model-loading (J) and streaming (M) into separate objects is safe only
   if each keeps owning and incrementing its own counter and the
   by-value-capture pattern is preserved exactly.
3. **Composer/model sensitivity is a de facto state machine with no
   single owner.** Four flags (`_streaming`, `_loading_model`,
   `_load_failed`, `_ollama_cli_busy`) drive widget sensitivity from four
   different call sites with three different techniques (a general
   sensitivity setter, a busy-flag setter, and two inline blocks). This
   is not a behavior bug today (the suite passes), but it is a real
   extraction hazard: splitting groups I/J/K/M apart without first naming
   this as one state machine risks each extracted piece re-deriving
   sensitivity slightly differently. This audit does **not** propose
   fixing it now — only flags it as something a later phase should
   consolidate deliberately, as its own reviewable change, not as a side
   effect of an unrelated extraction.
4. **`_messages` has no single owner.** Ten methods across F, L, and M
   mutate it directly via list slicing/append/in-place edits rather than
   through a shared helper: `clear_chat` (F), `new_chat` (F),
   `switch_conversation` (F), `_restore_history` (F), `_delete_message`
   (L), `_drop_messages_from` (L), `_regenerate_message` (L),
   `_edit_resend_message` (L), `_send` (M), `_commit_assistant_result`
   (M). An extraction that splits "conversation management" from
   "message actions" from "streaming" needs an explicit decision about
   which object owns `_messages` and which others get a read-only view or
   a narrow mutation API. **Resolved in the phase plan:** §7 Phase 22
   (conversation-lifecycle extraction) is assigned to make this decision
   and establish the canonical owner + mutation interface; Phases 24
   (message actions) and 26 (streaming) consume that interface rather
   than each mutating the raw list.
5. **`_apply_health`'s UI-state application is untested** (confirmed via
   test audit, §7) even though `classify_error`/`probe_ollama` themselves
   are well unit-tested in isolation. Extracting group I without first
   adding a characterization test risks a silent behavior change that no
   existing test would catch.

---

## 6. Existing characterization tests and coverage gaps

### 6.1 What each of the 15 scripts actually exercises

| Test file | Real `ChatSidebar` instance + GLib loop? | What it actually characterizes | Confidence for window.py |
|---|---|---|---|
| `test_generation_lifecycle.py` | Yes | `_start_assistant_stream`, `switch_conversation` mid-stream, `_invalidate_active_stream`, `_request_stop`, stale-completion guards | **Direct, strong** — the best-covered part of the file |
| `test_restore_scroll.py` | Yes | `switch_conversation` → `_apply_restored_transcript`/`_restore_history`, scroll/batch behavior | Direct (narrow) |
| `test_sidebar_interactions.py` | Yes (x2 windows) | `toggle_sidebar`, model dropdown wiring, `_refresh_models` → `_on_model_selected` → `_begin_model_load` → `_save_last_model` chain, `_rebuild_history_list`, pointer-cursor styling, sidebar-starts-closed regression | Direct — broadest UI-wiring coverage |
| `test_markdown_sanitization.py` | Yes | `switch_conversation` restore path + `_start_assistant_stream` (fake `chat_stream`) as harnesses to reach transcript sanitization | Direct, but the target under test is `transcript_view.py`/`app.js`, not `window.py` logic |
| `test_wire_code_ui_batch.py` | Yes | Same restore-path harness, verifying batched code-UI wiring | Direct (narrow), same caveat |
| `test_message_actions.py` | **No** | Module-level helpers only (`join_continue`, `continue_seed_for_stream`, `_is_ephemeral_greeting`) + `ConversationStore` directly, plus a hand-rolled *simulation* of the regenerate-truncate logic (not a call into `_regenerate_message`) | **Incidental** — despite the name, none of `_delete_message`/`_regenerate_message`/`_edit_resend_message`/`_continue_message` is ever called on a real `ChatSidebar` |
| `test_multichat.py` | No | `ConversationStore` multi-conversation logic directly | Incidental to `ChatSidebar.switch_conversation`/`export_conversation`/`delete_conversation`, which wrap this store but are never called here |
| `test_ollama_health.py` | No | `ollama_health.py` classification/probing in isolation (mocked `OllamaClient`) | Incidental — `_apply_health`/`_on_ollama_probe` consume this module but are never invoked |
| `test_stream_cancellation.py` | No | `OllamaClient.chat_stream` cancellation at the HTTP/socket layer | Incidental — `ChatSidebar`'s use of this (via `_request_stop`/`_invalidate_active_stream`) is characterized separately, in `test_generation_lifecycle.py` |
| `test_web_content_security_policy.py`, `test_web_navigation_policy.py` | Real WebKit view, but no `ChatSidebar` | `transcript_view.py` / `web/app.js` CSP and navigation confinement | Not a `window.py` test |
| `test_dependency_declaration.py`, `test_installed_layout.py`, `test_desktop_integration.py`, `test_release_identity.py` | No | Packaging, meson install, desktop/AppStream metadata, `main.ChickenButtApp` identity | Not `window.py` tests |
| `scripts/smoke_gui.py` (CI-excluded, needs live Ollama) | Yes | `_begin_model_load` across model switches, `clear_chat` | Direct but not part of the enforced suite |

### 6.2 Coverage by responsibility group

| Group | Covered? | Gap |
|---|---|---|
| C — UI construction | Indirect (sidebar_interactions exercises some wiring) | `_build_ui`/`_build_load_overlay` layout details, `_show_empty_state`/`_render_empty_transcript` native path |
| D — Composer geometry | **None** | No test touches `_apply_composer_height`, `_composer_max_visible_lines`, char counter, hint fade |
| E — Sidebar/history UI | Direct (`_rebuild_history_list`, `toggle_sidebar`) only — **correction, round 7**: confirmed no test asserts on `_refresh_chat_title` (incl. its loading/streaming guard), `_select_active_history_row`, `_on_history_row_activated`, or the `_history_dirty` short-circuit itself (`test_sidebar_interactions.py:279` only *sets* the flag as setup) | `_make_chat_actions_popover`, `_refresh_chat_title`, `_select_active_history_row`, `_on_history_row_activated`, `_history_dirty` short-circuit — five of eight group-E methods effectively unexercised |
| F — Conversation management | Direct for `switch_conversation`; **none** for `new_chat`, `clear_chat`, `delete_conversation` (UI flow), `_confirm_delete_conversation` | Real gap — these are exactly the methods most likely to move in an early phase. **Correction, round 7**: also untested — the persistence-failure-ordering asymmetry (`switch_conversation` continues past a `set_active` failure; `delete_conversation` aborts past a `delete_conversation` store failure, `window.py:1966-1968` vs. `1926-1929`) |
| G — Export | **None** at `ChatSidebar` level (store-level export tested via `test_multichat.py`) | `export_conversation`/`_safe_export_basename`/file-dialog flow never exercised |
| H — Settings | **None** | `open_settings` dialog untested (low risk, minimal logic) |
| I — Model health/probing | Mixed: load *chain* covered (sidebar_interactions), `_apply_health`'s UI application **not** asserted anywhere | Real gap. **Correction, round 7**: `_on_health_action`'s three branches (`refresh`/`retry_load`/`dismiss`) and `_preferred_model` are also completely untested — confirmed zero references to either in any script beyond `HealthState.action` value checks in `test_ollama_health.py`, which test `ollama_health.py`, not `ChatSidebar._on_health_action` |
| J — Model loading | Direct (sidebar_interactions, smoke_gui) | `_update_load_progress`/pull-progress formatting paths |
| K — Composer CLI commands | **None** | `_run_ollama_pull`/`_run_ollama_info`/`_try_composer_command`/`_format_pull_progress`/`_composer_cmd_busy`/`_set_composer_cmd_busy`/`_post_status_message`/`_update_status_message` — all eight group-K methods untested |
| L — Message actions | **None** at `ChatSidebar` level (only the pure-function halves and store ops) | Real gap — highest-value gap to close before touching this group |
| M — Streaming | **Correction, round 7**: `test_generation_lifecycle.py` characterizes `_start_assistant_stream`/`switch_conversation`/`_invalidate_active_stream`/`_request_stop` strongly, but its own helper function's docstring says it exists to "mirror what `_send()` does, minus composer/health/model UI guards" (`scripts/test_generation_lifecycle.py:148`) — `_send` itself (empty-input guard, composer-command routing, unhealthy-reprobe branch, missing-model guard, and the append/persist/start sequence) has **zero** direct coverage, not just "indirect" | `_send`'s own guards and routing; non-cancellation error paths mid-stream; `_commit_assistant_result` replace/continue branches only exercised indirectly (never to a completed commit) |
| N — Native transcript rendering | **None** — every ChatSidebar-constructing test runs in the default `webkit` mode | `_append_message`, `_native_action_bar`, `_native_edit_user`, `_native_remove_message` are effectively unexercised by the enforced suite |
| O — Web-intent bridge | Indirect only | Dispatch table itself (`_on_web_intent`) not directly asserted |

**Headline gaps, in priority order for characterization work:** (1) native
transcript mode (`CHICKENBUTT_TRANSCRIPT=native`) is essentially untested
by the enforced suite even though it's a fully supported, documented mode
(`README.md`); (2) message actions (edit/delete/regenerate/continue) have
no `ChatSidebar`-level test despite a file named exactly for that purpose;
(3) `_apply_health`'s UI application; (4) conversation lifecycle UI flows
(`new_chat`, `clear_chat`, `delete_conversation`, export).

---

## 7. Proposed extraction phases (proposals, not decisions)

**Revision history of this section:** round 1 fixed three oversized
phases (~500-750 method-lines each) and a monolithic characterization
phase by splitting into eleven narrower ones with just-in-time tests.
Round 2 fixed a repeat of the monolithic-test problem in one place, an
underspecified composer extraction interface, two misassigned method
owners, three methods miscategorized as mode-agnostic when they're
native-transcript-specific, one unsupported cross-phase dependency, and
loose behavior-change wording — landing on fourteen phases. **Round 3**
found that round 2's "tests immediately before the phase they protect"
principle was still applied inconsistently (Phases 1-5 bundled tests with
extraction while later phases split them), that four specific gaps
already named in §6.2 never became actual phases (conversation-lifecycle
UI flows, `_make_chat_actions_popover`, `_on_web_intent` dispatch,
streaming's non-cancellation error path), that `_messages` ownership
(§5 risk 4) was flagged as a problem but never assigned an owner in the
plan, that moving the native action-bar methods into the transcript
adapter (round 2) would drag message-action business logic and direct
`_messages` reads into the adapter unless an intent-dispatch interface is
specified, and that two further extraction seams (export's title
dependency, the CLI-busy flag's direct sensitivity writes) needed the
same "narrow interface, not raw ownership" treatment already applied
elsewhere. This is the round-3 structure: every extraction phase now has
its own standalone, immediately-preceding characterization phase, with no
bundled exceptions — 22 phases in 11 test/extract pairs. Rounds 4-7 found
further corrections (model-state ownership overlaps, an oversized
transcript-adapter phase requiring a three-way split, misattributed
citations, message-ID allocation ownership, and several under-scoped
characterization phases) — see the revision notes at the top of this
document for the full account of each round. **The current structure is
26 phases in 13 test/extract pairs.** None of this is authorized until
Scott approves it in `REFACTOR_PLAN.md`.

**A firm rule, not an open question:** every phase below preserves
current behavior exactly. Where this audit has found existing behavior
that looks incomplete or inconsistent (`_on_ollama_probe`'s missing
generation guard, the four-flag sensitivity logic in §5 risk 3), the
corresponding extraction phase documents and preserves that behavior
as-is. Changing it is never a sub-option inside an extraction PR — the
ground rules already forbid mixing behavior change with structural
extraction — it can only happen as its own, separate, explicitly
authorized PR, decided on its own merits after the extraction that
exposed it has already landed.

**Phase 1 — Settings characterization (test-only).** Direct unit tests
covering every moved behavior, not just `_pick_startup_model`:
`_read_settings`/`_write_settings` read/write-failure handling (missing
file, corrupt JSON, unwritable directory), `_load_last_model`,
`_save_last_model` (whitespace handling, no-op preservation when the
value is unchanged), and `_pick_startup_model` (exact match, soft
base-name match, no match). Risk: n/a (test-only). Verification: new
tests pass against current `main` unmodified.

**Phase 2 — Settings extraction (group A subset).**
`_read_settings`/`_write_settings`/`_load_last_model`/`_save_last_model`/
`_pick_startup_model` take no `self` and have no `ChatSidebar` coupling
at all — the lowest-risk starting point. Preserve re-export compatibility
for anything that still imports them from `window`. Risk: negligible.
Verification: full suite + Phase 1 tests passing unmodified.

**Phase 3 — Composer geometry characterization (test-only).** No
automated coverage exists for this group at all today. Must match the
full scope of what Phase 4 actually moves, not just the headline
resize math: `_apply_composer_height`/`_composer_max_visible_lines`
sizing, the char counter, **character-cap truncation** (`_on_composer_insert_text`'s
paste-clamping and `_on_buffer_changed`'s over-limit deletion),
**placeholder visibility** (`_on_buffer_changed` toggling
`self._placeholder`'s visibility on empty/non-empty text), **scrollbar
policy transitions** (`_apply_composer_height`'s `_input_scroll.set_policy(...)`
switching between `NEVER`/`AUTOMATIC` as content crosses the visible-line
cap), and the **alignment-callback interaction** (`_apply_composer_height`
and `_on_buffer_changed` both invoking `_sync_composer_action_valign`,
directly and via `GLib.idle_add` respectively).

**Correction (round 8):** the surface-layout hook and geometry fallbacks
are part of the moved behavior too. Characterize hook retry when no
surface is available, idempotence once connected, the immediate height
reapplication after connection, later layout-event reapplication, and
the line-height/content-height/window-height fallback paths. Risk: n/a
(test-only). Verification: new tests pass against current `main`
unmodified.

**Phase 4 — Composer geometry/character-cap extraction only.** Covers
*only* `_hook_composer_surface_layout`, `_composer_line_height_px`,
`_composer_max_visible_lines`, `_composer_content_height_px`,
`_apply_composer_height`, `_update_composer_char_counter`,
`_on_composer_insert_text`, `_on_buffer_changed`. Per the corrected group
D description in §2, this is *not* as clean an isolation as "only touches
`self.input`" — the extracted object must be given, explicitly: a
constructor-injected reference to `self._placeholder` (built in
`_build_ui`, group C, not `__init__`); ownership of
`self._composer_truncating` and `self._composer_layout_hooked` as its own
instance state; and a constructor-injected callback for the alignment
concern, since `_sync_composer_action_valign`/`_composer_hint_should_show`/
`_sync_composer_hint`/`_on_input_key` stay on `ChatSidebar` (they touch
`send_btn`/`stop_btn`/`_messages`/`_send` — group M/F territory, not
geometry) and both `_apply_composer_height` and `_on_buffer_changed` call
into that alignment method today.

**Correction (round 8):** the extracted object must also receive narrow
providers for the compositor surface, current window height, and default
window size instead of reaching back into `ChatSidebar` for
`get_surface()`, `get_height()`, or `get_default_size()`. Phase 4 must
rewire every construction-time connection that currently targets the
moved methods: the initial height application, the buffer's `changed`
and `insert-text` signals, and the window's `realize` and `map` signals.
Risk: low, but only if the interface above is explicit. Verification:
full suite + Phase 3 tests + manual resize check.

**Phase 5 — Export characterization (test-only).** Currently zero
automated coverage of `export_conversation`/`_safe_export_basename` at
the `ChatSidebar` level. Add tests covering both formats (md/json),
format normalization and unsupported-format fallback, basename
sanitization and title/message-excerpt fallback, and a missing
conversation.

**Correction (round 8):** characterize the asynchronous dialog/write
lifecycle as well: dialog cancellation and non-cancellation errors,
`None` file and missing-path no-ops, successful UTF-8 output, and write
failure logging plus user-visible error dialog. Risk: n/a (test-only).
Verification: new tests pass against current `main` unmodified.

**Phase 6 — Export extraction, via an injected title provider.**
`export_conversation`/`_safe_export_basename` depend only on
`ConversationStore` and the window (file dialog `transient_for`), *and* on
`_conversation_display_title`. That method (`window.py:1798`) is also
used by `_confirm_delete_conversation` (`window.py:1897`) and reads
`self._conversation_id`/`self._messages` in its fallback path — it stays
with conversation management (group F, Phase 22), not export. So the
extracted export code must take a `title_provider: Callable[[str], str]`
constructor argument (defaulting to a bound `_conversation_display_title`)
rather than either reaching back into `ChatSidebar` or owning the title
logic itself — this inverts the dependency correctly without requiring
`_conversation_display_title` to move. The exporter also receives the
store and transient-parent dependencies explicitly.

**Correction (round 8):** retain `ChatSidebar.export_conversation` as an
intentional thin delegator. The two window actions and two history-popover
callbacks currently share that stable entrypoint; forcing all four to
know the exporter object would widen the extraction for no benefit. When
Phase 22 moves `_conversation_display_title` and the active-conversation
projection, it must rebind the injected title provider and assert in an
integration test that export sees the migrated projection. Risk:
low-medium. Verification: full suite + Phase 5 tests passing unmodified.

**Phase 7 — Health/probe characterization (test-only), covering all of
Phase 8's methods, not only `_apply_health`.** Add a deterministic
(fake-client, no network) test for `_apply_health`'s UI application and
for probe-ordering/staleness — the test documents current behavior
(`_on_ollama_probe` has no generation guard at all, §4.3: last-probe-wins,
no staleness protection) rather than the initial draft's incorrect claim
that it's protected.

**Correction (round 7):** confirmed by direct search that `_on_health_action`'s
three branches (`"refresh"`/`"retry_load"`/`"dismiss"`, `window.py:2528-2545`)
have zero direct coverage — `test_sidebar_interactions.py:269` only
checks the health-action *button*'s pointer-cursor styling, never clicks
it or asserts on the branch taken; `test_ollama_health.py` tests
`HealthState.action` values from `classify_error`, not `ChatSidebar`'s
handling of them. `_preferred_model` (`window.py:2547`) and the
model-selection edge cases in `_select_model_name`/`_on_model_selected`
(exact match, soft base-name match, retry-after-failure, ignoring
truncated-error strings stuffed into the dropdown) are equally untested.
Since Phase 8 moves all of group I together, this phase's scope must
cover all of it.

**Correction (round 8):** make that completeness mechanically
checkable, branch by branch: `_refresh_models`' loading no-op;
`_apply_health`; current last-probe-wins ordering and every
healthy/no-model/unavailable/error transition; all three
`_on_health_action` branches; `_preferred_model` store priority and
exception fallback; and `_select_model_name`/`_on_model_selected`
exact/soft/no-match, placeholder/error, same-model, retry, warm/no-warm,
and load-in-progress paths. Risk: n/a (test-only). Verification: new
tests pass against current `main` unmodified.

**Phase 8 — Health/probe extraction, excluding `_set_load_controls_sensitive`
and *not* claiming ownership of model-session state.** Extract
`_refresh_models`, `_on_ollama_probe`, `_apply_health`, `_on_health_action`,
`_preferred_model`, `_select_model_name`, `_on_model_selected` (group I)
behind a narrow callback interface. `_set_load_controls_sensitive` does
**not** move here — per the §2 ownership correction, it's shared
composer/nav/sidebar enablement policy called by both groups I and J, not
health-specific; it stays window-owned until Scott decides whether/how to
consolidate the four-flag sensitivity logic (§5 risk 3), which is out of
scope for this phase regardless.

**Correction (round 5):** verified that `self._model` is written directly
by three of this phase's own methods — `_select_model_name`
(`window.py:2020,2039,2041`), `_on_model_selected` (`window.py:2407`),
and `_on_ollama_probe` (`window.py:2442,2452`) — and `self._load_failed`
is written by `_on_ollama_probe` too (`window.py:2433,2451`). But
`_on_model_load_finished` (group J, Phase 10) writes both of those same
fields as well (`window.py:2788-2789,2815`). **This phase must not claim
ownership of `_model`/`_load_failed`/`_loading_model`/`_load_generation` —
that joint ownership is resolved in Phase 10, not here.** Phase 8's
extracted health/probe controller reads and writes these fields via
narrow callbacks (e.g. `get_active_model()`/`on_model_chosen(name)`/
`get_load_failed()`) into whatever currently owns them — which at this
point in the sequence is still `ChatSidebar` directly, since Phase 10
hasn't run yet. Phase 10 later migrates this phase's callback wiring onto
the canonical model-session interface it establishes (see Phase 10).

**Correction (round 8):** this controller owns all of its private
health/probe state: `_health`, `_suppress_model_select`,
`_health_action_id`, and `_health_action_model`. Its narrow contract must
explicitly supply nullable current-model get/set, loading/failed reads,
failed-state write, and begin-load callbacks; message-empty and active-
conversation model-preference providers; status, overlay-hide, shared-
sensitivity, send-sensitivity, and input-sensitivity callbacks; and the
client, model selector, refresh control, health banner/title/detail/action
controls, and settings fallback. Phase 10 rebinds the model-session
callbacks to its new owner; Phase 22 rebinds message/conversation
providers to its projection. Risk: medium. Verification: full suite +
Phase 7 tests passing unmodified.

**Phase 9 — Model-load characterization (test-only).**
`test_generation_lifecycle.py` does not cover `_load_generation`/
`_begin_model_load` at all (confirmed via its own docstring scope and a
direct search of the file finding zero references) — the only exercise of
repeated model loads is `scripts/smoke_gui.py`, excluded from CI. Must
cover the full scope of what Phase 10 moves, not only ordering: a
deterministic test for stale-load-can't-clobber-a-newer-load, **plus**
`_update_load_progress`'s NDJSON-chunk-to-progress-bar mapping (already
named as a gap in §6.2's group-J row: "`_update_load_progress`/pull-progress
formatting paths") and `_on_model_load_finished`'s success/failure
completion UI — button re-enablement, health-state update on both
outcomes, and the greeting trigger on success.

**Correction (round 8):** the complete characterization also includes
empty-model and streaming no-ops; stale status, chunk, and finish
callbacks; cancellation/generation replacement; one-pulse-only start,
stop, hidden-overlay termination, and determinate/indeterminate
transitions; sensitivity ordering; last-model and conversation-model
persistence ordering plus failure continuation; repeated-load greeting
deduplication; and the exact reset placement in `clear_chat`, successful
`new_chat`, and `switch_conversation`, including that the already-empty
`new_chat` branch does not reset. Risk: n/a (test-only). Verification:
new tests pass against current `main` unmodified.

**Phase 10 — Model-load extraction, excluding `_set_load_controls_sensitive`
and `_show_ephemeral_greeting`, and becoming the canonical owner of
model-session state.** Extract `_show_load_overlay`, `_start_load_pulse`,
`_stop_load_pulse`, `_hide_load_overlay`, `_update_load_progress`,
`_begin_model_load`, `_on_load_status`, `_on_load_chunk`,
`_on_model_load_finished` (group J) behind the same kind of callback
interface as Phase 8. `_show_ephemeral_greeting` does **not** move here —
per the §2 ownership correction, its body writes directly into the
transcript and it's called just as often by group F
(`clear_chat`/`new_chat`/`switch_conversation`) as by
`_on_model_load_finished`; the extracted loader should expose an
"on ready, should-greet" callback and let `ChatSidebar` (still owning
transcript presentation) decide whether to call
`_show_ephemeral_greeting`.

**Correction (round 5) — resolving the Phase 8/10/18 model-state
overlap:** `self._model`, `self._loading_model`, `self._load_failed`, and
`self._load_generation` are jointly written today by both this group
(`_on_model_load_finished`) and Phase 8's group
(`_select_model_name`/`_on_model_selected`/`_on_ollama_probe`), and the
conversation projection (now Phase 22) was previously (incorrectly)
described as also covering the active conversation's "model" — three
phases with overlapping claims on the same concept. Resolved as:
**Phase 22 owns only conversation ID + messages** (the per-conversation
model preference stays a plain `ConversationStore.set_model`/`conv.model`
read/write, not shadowed by the in-memory projection); **Phase 8 owns
none of `_model`/`_loading_model`/`_load_failed`/`_load_generation`** (see
Phase 8's correction above); **this phase (10) becomes the sole canonical
owner of that model-session state**, exposing queries (e.g.
`current_model`, `is_loading`, `has_failed`) and mutation entrypoints.
It also owns the loader-private `_stop_load`, `_load_pulse_id`, and
`_load_indeterminate`; no other group reads those fields, so they need no
compatibility surface.
Because Phase 8 already landed with callbacks pointed at raw `ChatSidebar`
attributes, this phase's own scope includes migrating those
already-extracted callbacks onto the new model-session interface — the
same already-extracted-consumer migration pattern used for the
`_messages` facade (see Phase 22's general migration invariant, which
applies here too).

**Correction (round 6) — `_greeted_models` ownership.** Per §3's
correction, this dedup set is cleared by group F
(`clear_chat`/`new_chat`/`switch_conversation`) and read + mutated only
by this group's `_on_model_load_finished` — group I never touches it.
This phase becomes its owner too (it's model-load-completion bookkeeping,
not health/probe), exposing **`reset_greetings()`** and internally
deciding — via the existing "on ready, should-greet" callback — whether a
given model warrants a greeting, mirroring the current `if greet and
model not in self._greeted_models and not self._messages` check
(`window.py:2837`). Note the `not self._messages` half of that condition
is itself a `_messages` read this phase currently makes directly; per
Phase 22's migration approach (see Phase 22's round-6 correction), this
call site is one more the general read-only-consumer migration list
should pick up.

**Correction (round 8):** Phase 10 must immediately replace the three
existing direct clears in `clear_chat` (`window.py:1543`), successful
`new_chat` (`1611`), and `switch_conversation` (`1970`) with calls to
`reset_greetings()` at those exact branch positions. Deferring that
rewiring until Phase 22 would leave an invalid twelve-phase interval in
which the new owner and the old group-F writers diverge. The
already-empty `new_chat` branch (`1587-1596`) must remain a no-reset
path.

Phase 10 also installs read-only delegating `ChatSidebar` compatibility
properties for `_model`, `_loading_model`, and `_load_failed`, because
unmigrated consumers remain in sidebar/title, conversation lifecycle,
message actions, CLI/status, and streaming code. `_load_generation` and
the loader-private fields remain internal. Phases 18, 20, 22, 24, and 26
migrate their inventoried readers; Phase 26 performs the required
whole-file raw-reference inventory, rewires any retained window
consumers such as `_set_load_controls_sensitive`, and removes the three
properties only after the inventory proves zero consumers. Depends on
Phase 8 (shares the health-state interface for load failures, and is the
phase whose callback wiring gets migrated here). Risk: medium.
Verification: full suite + Phase 9 tests passing unmodified.

**Phase 11 — Transcript reset/replay/removal characterization
(test-only).** First of three native-transcript slices (**correction,
round 7**: what was one oversized Phase 11/12 pair — 13 methods, ~705
method-lines including the 254-line `_start_assistant_stream`, verified
by direct measurement — is now three narrower test/extract pairs matching
the three coherent slices the round-6 draft already identified but only
let Scott split at the PR-packaging level; splitting the *implementation*
into three separate phases is required, not optional, given that size).
This slice covers: **reset/empty-state** (`_render_empty_transcript`,
`_show_empty_state`) and **replay-from-restore**
(`_apply_restored_transcript`) and **removal**
(`_delete_message`/`_drop_messages_from`'s `message_removed` posts vs.
`_native_remove_message`). Native mode (`CHICKENBUTT_TRANSCRIPT=native`)
has no coverage in the enforced suite, and it cannot be added by simply
running the existing suite under that environment variable:
`test_restore_scroll.py:116`, `test_markdown_sanitization.py:248`, and
`test_wire_code_ui_batch.py:116` all hard-block on `win._web is not None
and win._web._ready`, true only in WebKit mode — they'd fail, not pass or
skip, under native mode. Risk: n/a (test-only). Verification: new tests
pass against current `main` unmodified; full (WebKit-mode) suite still
green.

**Correction (round 9):** Phase 11 must also force
`WebTranscriptView` construction to fail after the requested mode starts
as `webkit`. Backend choice is not final until `_build_ui` catches that
failure and changes `_transcript_mode` to `native`
(`window.py:796-829`). The test preserves today's exact fallback,
including the fact that `ensure_md_css()` is called only before
`_build_ui` when the initially requested mode is already native
(`window.py:567-569`), not after a WebKit construction failure. It must
then exercise reset/replay/removal against the fallback-native sink.
Also assert replay's default role/content handling, missing-ID allocation,
empty-state and `_native_rows` transitions, not merely final visible
rows.

**Phase 12 — Transcript adapter seam: reset, replay, removal.**
Addresses §4.2 directly for this slice: formalize the `webkit`/`native`
branch for `reset`/replay/`remove_message` as an object (e.g.
`TranscriptSink`) with two implementations wrapping the current
`_web`/`chat_box` code paths verbatim — no behavior change, pure seam
introduction for this slice. `_native_remove_message` moves into the
native implementation here (it's pure rendering — pops
`self._native_rows` and removes the widget, no message-action calls or
`_messages` reads, unlike the two methods handled in Phase 16). Requires
Phase 11. Risk: medium (breadth within this slice only). Verification:
full suite (WebKit mode) + Phase 11's tests, run directly.

**Correction (round 9) — dependency-closed foundation and single state
owner.** Phase 12 selects/constructs the sink only after the WebKit
constructor either succeeds or falls back. It establishes one canonical
owner for the selected backend and, on native, the widget/scroller/box,
`_native_rows`, and empty/icon/title/subtitle state. No mutable container
is copied or exposed as a raw compatibility property. The retained
style-manager callback reaches the icon through the owner interface.

Replay cannot wait for Phase 16: `_apply_restored_transcript` currently
calls `_append_message` and `_next_msg_id` (`window.py:2177-2181`), and
Phase 14 status rendering needs row construction too. Phase 12 therefore
introduces the lowest-level native row primitive needed by replay/status,
with any action-bar concern still awaiting Phase 16 supplied through a
narrow temporary factory rather than a broad window reference. Its
message-ID provider initially binds to the unchanged
`ChatSidebar._next_msg_id` and is re-bound in Phase 22.

Moving `_native_remove_message` does not remove its window signature:
callers remain in K/L/M until Phases 20/24/26. Phase 12 installs explicit
delegators for every retained transcript entrypoint and records their
last consumer; raw F clears/resets are redirected to the owner
immediately. Transcript delegators are removed only in Phase 26 after a
whole-file inventory proves no caller remains.

**Phase 13 — Status-message and greeting characterization (test-only).**
Second of the three native-transcript slices: **status-message
create/update** (the CLI commands' `_post_status_message`/
`_update_status_message`, which post `message_added`/`message_reset`/
`message_done` events or their native equivalent) and **the ephemeral
greeting** (`_show_ephemeral_greeting`'s `empty_state` post vs. native
empty-box text swap). Both backends. Risk: n/a (test-only). Verification:
new tests pass against current `main` unmodified.

**Correction (round 9):** assert that status rows remain non-persisted,
retain the same allocated ID across update/done, and use Phase 12's
native row foundation. Greeting coverage includes the empty-state
presence/recreation branches, title/subtitle substitution, and the
separate send-button enablement that remains outside the sink.

**Phase 14 — Transcript adapter seam: status messages and greeting.**
Formalizes the `webkit`/`native` branch for the status-message and
greeting surface as part of the same `TranscriptSink` object Phase 12
introduced. `_post_status_message`/`_update_status_message` (group K) and
`_show_ephemeral_greeting` (retained on `ChatSidebar` per §2's ownership
correction) are rewired to call the sink instead of branching inline —
ownership of these methods themselves doesn't move, only their internal
transcript-mode branching does. Requires Phase 12 (shares the sink
object) and Phase 13. Risk: medium. Verification: full suite + Phase 13's
tests.

**Correction (round 9):** Phase 14 extends the single owner created in
Phase 12; it does not acquire separate copies of `_empty_box`,
`_empty_title`, `_empty_sub`, or `_native_rows`. Status create/update uses
the Phase-12 row primitive, while `_show_ephemeral_greeting` retains its
message-policy and send-sensitivity work and delegates only transcript
presentation.

**Phase 15 — Streaming-update/finalization and native-intent
characterization (test-only).** Third and riskiest of the three
native-transcript slices: **streaming update/finalization**
(`_start_assistant_stream`'s `flush_stream`/`finalize_ui` posting
`message_delta`/`message_done`/`message_error` vs.
`body.append_stream`/`finish_stream`/`set_plain`) and **native message-row
rendering + intent dispatch** (`_append_message`, `_native_action_bar`,
`_native_edit_user`). Both backends. Risk: n/a (test-only). Verification:
new tests pass against current `main` unmodified.

**Correction (round 9):** enumerate the protocol Phase 16 will introduce:
new/replace/continue begin behavior; native `_render_serial`
currentness/stale-handle rejection; paced and leftover deltas;
error-with/without-partial-text, empty response, and successful
finalization; replacement of the temporary native row with its final
action-enabled row; scroll scheduling; and copy/edit/action intent
payloads, including native edit-dialog cancel, empty-save, and valid-save
branches.

**Phase 16 — Transcript adapter seam: streaming updates/finalization and
native intent dispatch.** Completes the `TranscriptSink` object with the
streaming-update surface, and gives the native message-row renderer an
intent-dispatch interface mirroring `WebTranscriptView`'s. As read today,
`_native_action_bar` calls `self._regenerate_message`/
`self._delete_message`/`self._continue_message` directly and reads
`self._messages` via `self._find_message_index` (`window.py:3281-3283`),
and `_native_edit_user` calls `self._edit_resend_message` directly
(`window.py:3396`). Moving these into the adapter **must not** carry that
direct-call/direct-read pattern with them — that would make the "pure
rendering" adapter own message-action business logic and conversation
state, defeating the point of the seam. Instead, both must be constructed
with the same kind of `on_intent` callback `WebTranscriptView` already
uses (`transcript_view.py` — the WebKit side already posts
`copy_text`/`regenerate`/`continue`/`delete_message`/`edit_resend`
intents through exactly this pattern via `_on_web_intent`); the
action-bar buttons emit intents through that callback instead of calling
group-L methods, and `current_text()`'s lookup is satisfied via an
injected accessor rather than direct `self._messages` indexing. This
makes the two transcript backends symmetric for the first time and gives
Phase 24 (message actions) one dispatch path to own instead of two. This
is a larger seam-introduction step than "wrap verbatim" — it changes *who
calls whom* for the native action bar without changing any observable
behavior — so it should be reviewed with that in mind. Requires Phase 12,
Phase 15. Risk: medium-high (this slice carries the riskiest rewiring of
the three). Verification: full suite (WebKit mode) + Phase 15's
native-mode tests, run directly (not via a blanket env-var re-run of the
WebKit-assuming scripts). Whether to also promote a standing native-mode
CI lane beyond these targeted tests is a decision for Scott, not assumed
here.

**Correction (round 9) — executable streaming/native contract.** The
sink returns an opaque stream handle from `begin`; it owns native
`_render_serial` and exposes `is_current(handle)`, paced `delta`, error,
finalize, and final-row-replacement operations. The streaming engine
never receives a `MessageBody` or reads backend internals. Scrolling and
empty/native-row state remain inside the Phase-12 owner.

Native row/action/edit construction receives explicit `on_intent`,
`current_text`, transient-parent, and message-ID providers. Phase 22
re-binds text/ID providers to its projection/allocation owner; Phase 24
re-binds intent dispatch to the extracted message-action owner. Public
window `_append_message`/`_native_remove_message` delegators remain only
for inventoried L/M callers through Phases 24/26, then retire at the
Phase-26 whole-file gate. This phase depends on Phase 14 as well as
Phases 12/15 because it completes the same progressively-built owner.

**Phase 17 — Sidebar/history-UI characterization (test-only), covering
all eight methods Phase 18 moves, not only the popover.**
`_make_chat_actions_popover` (export/delete menu wiring) has zero
coverage today — `test_sidebar_interactions.py` exercises
`_rebuild_history_list`/`toggle_sidebar` but never opens the popover or
asserts its buttons call the right handlers.

**Correction (round 6, renumbered):** confirmed by direct search that no
existing test asserts on `_refresh_chat_title` (including its "don't
clobber live status while loading/streaming" guard,
`window.py:1163-1165`), `_select_active_history_row`,
`_on_history_row_activated`, or the `_history_dirty` short-circuit in
`_rebuild_history_list` (`window.py:1641`) —
`test_sidebar_interactions.py:279` only *sets* `win._history_dirty = True`
as setup, it never exercises the already-clean short-circuit path. This
phase's scope must cover all four of those alongside the popover, since
Phase 18 moves all eight group-E methods together. Risk: n/a (test-only).
Verification: new tests pass against current `main` unmodified.

**Correction (round 9):** method bodies alone are insufficient because
Phase 18 must also rewire `_build_ui`/`_build_history_sidebar`. Cover
`_sidebar_syncing`'s recursion guard; the window action, toggle signal,
row-activation signal, and initial idle rebuild/title callbacks; title
loading/streaming guard, store fallback, and truncation; dirty/clean,
empty-list, list-error, selection, activation, and popover dispatch
branches. Assert exactly-once signal delivery so extraction cannot
double-connect retained and controller handlers.

**Phase 18 — Sidebar/history-UI extraction (group E), via injected
presenter callbacks, status accessors that consume already-landed
owners directly, and explicit `_history_dirty` ownership.**
`toggle_sidebar`, `_on_sidebar_toggled`, `_mark_history_dirty`,
`_refresh_chat_title`, `_rebuild_history_list`, `_select_active_history_row`,
`_on_history_row_activated`, `_make_chat_actions_popover`. **Correction
(round 2, still holds):** a direct search of all eight methods' bodies
found zero references to `_web`, `chat_box`, `_transcript_mode`, or
`_transcript_widget` — group E never touches transcript rendering and has
no hard dependency on the transcript-adapter phases. **Correction (round
3):** round 2's "plain method calls... valid regardless of extraction
order" understated what those calls need. As read today,
`_on_history_row_activated` calls `self.switch_conversation(cid)`
directly (`window.py:1739`), and `_make_chat_actions_popover`'s buttons
call `self.export_conversation(...)` and
`self._confirm_delete_conversation(...)` directly (`window.py:1782-1793`).
Once group E is its own object, it must not reach back into `ChatSidebar`
for these, nor rely on an unspecified "thin delegator" — it needs
constructor-injected presenter callbacks: `on_activate(conversation_id)`
(wired to `switch_conversation`), `on_export(conversation_id, fmt)`
(wired to `export_conversation`), and `on_delete(conversation_id)` (wired
to `_confirm_delete_conversation`). This mirrors the callback pattern
already required for Phases 8/10/20.

**Correction (round 7) — the round-6 fix for this phase had two factual
errors.** First: round 6 said the status accessors (`is_loading_model()`
etc.) would be "still window-owned at this point, becoming Phase 10's
territory later." That's wrong — Phase 10 (model-load extraction) is
numbered *before* this phase (18) in the sequence, so by the time this
phase runs, Phase 10 *has already landed* and is the canonical owner of
`_loading_model`/`_streaming`-adjacent state. `is_loading_model()` must
consume Phase 10's real interface immediately, not a placeholder callback
awaiting a later migration; `is_streaming()` is the one accessor that
genuinely is still window-owned at this point, since streaming extraction
is last (Phase 26) — that one *does* get migrated later, the same way
Phase 8's callbacks were migrated by Phase 10. Second: round 6 said
"`_history_dirty`'s ownership — verified every write site is group F."
That's backwards: the actual raw `self._history_dirty = ...` assignments
are in `__init__`/`_build_ui` (group C setup, `window.py:545,1003`),
`_mark_history_dirty` itself (`window.py:1157` — this method *is* the
setter, and it's a group-E method), and `_rebuild_history_list`
(`window.py:1664,1721`, resetting to `False` after a rebuild) — group F
never assigns the attribute directly, it only *calls*
`self._mark_history_dirty()` (`window.py:1555,1618,1930,1958,2003,2093,2110`).
The conclusion (group E/sidebar owns `_history_dirty`) still holds — if
anything it's more clearly correct now, since the actual assignment sites
were already in group E — but the round-6 evidence for it was wrong. This
phase makes the extracted sidebar object the owner of `_history_dirty`,
exposing `mark_dirty()` as its public API (already true in effect for
`_mark_history_dirty`/`_rebuild_history_list`'s own assignments);
`ChatSidebar._mark_history_dirty()` (still called throughout
not-yet-extracted group F code until Phase 22) becomes a thin one-line
delegator to it. The extracted object also takes a direct
`ConversationStore` reference (no ownership issue — that module's
ownership never changes, per §1) and `get_active_conversation_id()`
(still window-owned until Phase 22 — another callback migrated later, the
same pattern). Risk: medium. Verification: full suite + Phase 17 tests
passing unmodified.

**Correction (round 9) — construction and inbound compatibility.** The
sidebar controller owns `_sidebar_syncing` alongside `_history_dirty` and
receives the exact sidebar/toggle/history/title widget references it
needs; group C may construct those widgets, but it injects them once and
connects the action/signals/idle callbacks to the new controller.

Moving the eight methods does not make their retained callers disappear.
Phase 18 preserves explicit `ChatSidebar` delegators: `mark_dirty` and
rebuild through Phase 22's F migration, and title refresh through Phase
26 because retained `_set_status` calls it. `toggle_sidebar` either stays
as the intentional public window delegator or the window action is
rewired directly; the choice is recorded, not implicit. Phase 22 rebinds
only `on_activate`/`on_delete` and the active-ID provider. `on_export`
continues to target Phase 6's intentional stable delegator. Phase 10 is
a hard dependency for loading-state queries; Phase 6 need not be a hard
dependency merely to provide the export callback.

**Phase 19 — Composer-CLI-command characterization (test-only), covering
all eight methods Phase 20 moves, not just three entry points.**
`_try_composer_command`/`_run_ollama_pull`/`_run_ollama_info` (group K)
have zero coverage today.

**Correction (round 7):** naming only these three understated what Phase
20 actually moves — eight methods total. This phase's scope must also
cover: `_composer_cmd_busy`/`_set_composer_cmd_busy` (busy-state
sensitivity — send-button-only, per Phase 20's own correction),
`_format_pull_progress` (pull-progress line formatting), `_post_status_message`/
`_update_status_message` (status bubble create/update), error handling in
`_run_ollama_pull`/`_run_ollama_info` (the `OllamaError`/generic-exception
branches), and the successful-pull-triggers-refresh behavior
(`_run_ollama_pull`'s `done()` calling `self._refresh_models()` on
success, `window.py:3076`). Risk: n/a (test-only). Verification: new
tests pass against current `main` unmodified.

**Correction (round 9):** expand this into branch-level coverage:
non-command, pull/list/ps, unsupported-command help, and already-busy
routing; status-row non-persistence; progress formatting, duplicate
suppression, same-phase percentage replacement, 12-line rolling cap,
redundant-UI suppression, clean EOF without an explicit `success` chunk,
`OllamaError` and generic errors; and completion order (final row, clear
busy, then refresh on success or restore model status on failure).
Because Phase 20 immediately changes `_send`'s CLI integration, Phase 19
also characterizes its raw busy guard and command-dispatch call before
the rewire.

**Phase 20 — Composer-CLI-command extraction, with a narrow
`on_cli_busy_changed` callback — not a call to `_set_load_controls_sensitive`
— and a separate `on_pull_succeeded` hook.** `_try_composer_command`,
`_composer_cmd_busy`, `_set_composer_cmd_busy`, `_format_pull_progress`,
`_run_ollama_pull`, `_run_ollama_info`, `_post_status_message`,
`_update_status_message`. `_post_status_message`/`_update_status_message`
branch on transcript mode exactly like groups L/M do (confirmed: both
used exclusively within group K, no cross-use by M), so this depends on
the status-message transcript-adapter phase (14). **Correction (round
3):** round 2's "report through the window's existing sensitivity policy"
wording was too loose — verified that `_set_composer_cmd_busy`
(`window.py:2950-2960`) touches *only* `send_btn`, while
`_set_load_controls_sensitive` (the "existing sensitivity policy")
touches `input`, `model_combo`, `_refresh_btn`/`_refresh_action`,
`_clear_btn`, `_new_chat_btn`/`_sidebar_new_btn`/`_sidebar_btn`, and
`_history_list` as well. If this phase literally routed busy-state
through `_set_load_controls_sensitive`, it would newly disable all of
those during a CLI command — an accidental behavior change, not a
preserving extraction. The CLI controller must own only the
`_ollama_cli_busy` flag and report state through a new, narrow
`on_cli_busy_changed(busy: bool)` callback whose `ChatSidebar`-side
implementation reproduces *exactly* today's send-button-only behavior —
nothing broader. Separately, verified `_run_ollama_pull`'s completion
handler calls `self._refresh_models()` directly on success
(`window.py:3076`, a group I/Phase 8 method) — the extracted controller
needs a second callback (e.g. `on_pull_succeeded()`) for this, rather
than reaching back into the health/probe object. Depends on Phase 8 (for
that refresh hook), Phase 14 (status-message adapter), Phase 19. Risk:
low-medium. Verification: full suite + Phase 19 tests passing unmodified.

**Correction (round 9) — no invalid CLI interval.** Phase 20 owns
`_ollama_cli_busy` and exposes `is_busy()`/`try_command()`. It immediately
rewrites `_send`'s raw `getattr(..., "_ollama_cli_busy", False)` and
`self._try_composer_command(text)` calls (`window.py:3124,3132`) to those
interfaces; Phase 26 later preserves the calls rather than performing
the first migration. No duplicate flag or raw compatibility property is
left behind.

The controller contract also injects the client, Phase-14 transcript
status surface, Phase-10 current-model query, status callback, narrow
busy callback, Phase-8 pull-success refresh hook, scheduler/worker
boundary, and message-ID provider. The ID provider initially targets the
unchanged window allocator and is re-bound in Phase 22. Consequently
Phase 10 is an explicit dependency alongside Phases 8/14/19.

**Phase 21 — Conversation-lifecycle characterization (test-only),
including the persistence-failure-ordering asymmetry.** `new_chat`,
`clear_chat`, `delete_conversation`, and `_confirm_delete_conversation`
have no `ChatSidebar`-level test today — this is the headline gap named
in §6.2 that round 2's phase table never actually turned into a phase.
Add tests for: new-chat on an already-empty draft (no duplicate row),
clear-chat's persistence behavior, delete-conversation's active-vs-inactive
branches, and the empty-conversation-pruning behavior in
`switch_conversation`/`new_chat`.

**Correction (round 7):** confirmed a real, easy-to-accidentally-normalize
asymmetry: `switch_conversation` catches a `set_active` failure, logs it,
and **continues** — it still sets `self._conversation_id` and proceeds to
load messages (`window.py:1965-1969`, no `return` in the `except` block)
— while `delete_conversation` catches a `delete_conversation` store
failure, logs it, and **returns immediately**, aborting the rest of the
method (`window.py:1926-1929`, `return` inside the `except` block). A
naive conversation-state projection could easily make these operations
uniformly atomic (all-or-nothing) or uniformly best-effort (always
proceed), silently changing behavior that today is inconsistent on
purpose or by accident — either way, it's existing behavior this
extraction must preserve exactly, not something to "fix" as a side effect
of introducing a cleaner object. Add a test asserting each operation's
specific current behavior under a simulated store failure. Risk: n/a
(test-only). Verification: new tests pass against current `main`
unmodified.

**Phase 22 — Conversation-lifecycle extraction, establishing the
canonical message-state owner with a staged migration (not an immediate
cutover), message-ID allocation, and an explicit decision on
`_history_restored`.** `clear_chat`, `_active_chat_is_empty`, `new_chat`,
`switch_conversation`, `delete_conversation`, `_confirm_delete_conversation`,
`_conversation_display_title` (if not already settled in Phase 6),
`_ensure_conversation`, `_restore_history`, `_apply_restored_transcript`,
`_persist_message`. Per §5 risk 4, ten methods across groups F/L/M
currently mutate `self._messages` directly by list slicing/append/
in-place edits with no shared owner. **Must preserve the
persistence-failure-ordering asymmetry characterized in Phase 21 exactly**
— `switch_conversation` continuing past a `set_active` failure and
`delete_conversation` aborting past a store failure are both existing
behavior, not accidents to normalize.

**Correction (round 3):** round 2 described the destination (a single
canonical owner + narrow mutation interface) but not the migration path,
and at this point in the sequence groups L (Phase 24) and M (Phase 26)
have *not* been extracted yet — their methods still live on `ChatSidebar`
and still index/mutate the message list directly. This phase cannot
retroactively rewrite those not-yet-touched methods without exceeding its
own scope. The resolution has four explicit parts:

1. `ConversationStore` remains the canonical *persisted* storage — this
   phase changes nothing about what's written to SQLite or when.
2. This phase introduces the canonical **in-memory active-conversation
   projection** — an object owning what is today `self._messages` **and
   the active conversation id only** (not "model" — see the round-5
   correction below for why model-session state is deliberately excluded
   here), with the narrow mutation API (replace-on-switch/restore,
   append, truncate-from-index, get-by-id) that Phases 24 and 26 are
   meant to consume.
3. Because groups L and M still call `self._messages` directly at this
   point, this phase must expose a **temporary compatibility facade**.
   This needs both a getter *and a setter* — not just a read-through, per
   the round-6 correction below — since existing L/M call sites do
   whole-list *reassignment* (e.g. `self._messages = self._messages[:idx]`
   in `_delete_message`/`_drop_messages_from`/`_regenerate_message`,
   `window.py:2212,2239,2287`), not only in-place mutation. A property
   with a getter (returning the projection's live list) and a setter
   (replacing the projection's internal list with the assigned value)
   keeps every not-yet-migrated caller working unchanged, with zero
   duplicated storage (the facade is a view, not a copy) and zero
   behavior change. This facade is scaffolding, not the destination.
4. Phase 24 migrates group L's methods onto the narrow mutation API;
   Phase 26 migrates group M's methods onto it. See the round-6
   correction below for why, once this phase also migrates the read-only
   consumers it's already touching, removal is simpler than round 5
   assumed.

**Correction (round 5), part one — model is not this phase's to own.**
Round 3/4 said the projection owns "the active conversation id/model."
Verified: `self._model` is written directly by methods in *both* Phase 8
(`_select_model_name`, `_on_model_selected`, `_on_ollama_probe`) and
Phase 10 (`_on_model_load_finished`) — three phases cannot each claim
ownership of the same concept. Resolved: this phase owns **conversation
ID and messages only**. The per-conversation model preference is not new
in-memory state at all — it already round-trips through
`ConversationStore` (`conv.model`, `store.set_model(...)`) and stays that
way; live model-*session* state (`_model`/`_loading_model`/`_load_failed`/
`_load_generation`) is Phase 10's to own, not this phase's — see Phase
8's and Phase 10's corrections above.

**Correction (round 5), part two — a general migration invariant.**
Round 4's claim that "nothing will be left reaching for a raw
`self._messages` by [streaming extraction]" is false: a direct search
finds read-only `self._messages` access well beyond groups L and M.
**General migration invariant, applying to every staged migration in this
plan, not just this one:**

- An extracted owner exposes read-only queries (e.g. `is_empty()`,
  `snapshot()`, `current_model`, `is_loading`) or delegating
  compatibility properties for consumers that haven't migrated yet —
  it never requires them to migrate atomically with the owner's own
  introduction.
- Mutable state is never copied or duplicated between owners — exactly
  one object holds the real data at any point in the migration; every
  other reference is a view or a call-through, never a second copy that
  could drift out of sync.
- A facade (the temporary raw-access compatibility shim) is removed only
  after a direct-reference inventory — grep for the raw attribute/list
  across the *whole file*, not just the phases assumed to touch it —
  proves zero remaining consumers, mutating or read-only.

**Correction (round 6) — the round-5 reader inventory misattributed two
of its own citations, and put the migration work in the wrong phase.**
Re-checking each citation against this document's own phase definitions:
`_composer_hint_should_show` (`window.py:1357`) was cited as "the
composer-extraction phase," but that phase's own text explicitly
*excludes* it — it stays on `ChatSidebar` (it reads `_messages`, which is
group F/M territory, not composer geometry). `_show_ephemeral_greeting`
(`window.py:2851`) was cited as "the model-load-extraction phase," but
that phase's own text explicitly *excludes* it too — it also stays on
`ChatSidebar` (transcript presentation, called by both group F and
`_on_model_load_finished`). Both are retained-on-`ChatSidebar`
presentation methods, not code living inside some other phase's extracted
object — which changes who can fix them and when. The
`_select_model_name`/`_on_model_selected`/`_on_ollama_probe`/
`_on_health_action` (Phase 8) and `_on_model_load_finished` (Phase 10)
citations were correctly attributed, but per Phase 8's round-5 correction
these methods already read `_model`/`_load_failed` via injected callbacks
rather than raw attributes — the same should apply to their
`not self._messages` greet-decision checks (see Phase 10's round-6
`_greeted_models` correction), meaning only the *callback wiring*
`ChatSidebar` supplies to those already-extracted objects needs updating,
not the objects' own code.

**Resolved:** rather than deferring all of this to streaming extraction
(which would mean it reaching back to modify earlier phases' already-
landed controllers and unrelated retained presentation methods — exactly
what the invariant above is meant to prevent), **this phase migrates
every currently-known read-only consumer at the same time it introduces
the projection**, since all of it is either (a) `ChatSidebar`'s own code
(`_composer_hint_should_show`, `_show_ephemeral_greeting`, and this
phase's own `clear_chat`/`_active_chat_is_empty`/`new_chat`,
`window.py:1567,1574,1589`) — trivially in-scope, this phase already edits
`ChatSidebar` to add the projection — or (b) the callback-wiring
`ChatSidebar` passes into Phase 8/10's already-extracted objects
(`window.py:2045,2409,2446,2534,2837`) — also `ChatSidebar`-side glue, not
a change to those objects' internals.

**Correction (round 7) — the round-6 reader-migration list was still
incomplete.** Four more currently-known consumers need the same
treatment, all confirmed by direct search: (1) Phase 16's native
`current_text()` accessor (`window.py:3281-3283` via
`_find_message_index`) — an injected accessor this phase must re-bind
once it owns message lookup; (2) Phase 8's `_preferred_model`
(`window.py:2547-2556`), which reads `self._conversation_id` directly to
look up `conv.model`; (3) Phase 18's active-conversation-ID accessor
(`get_active_conversation_id`, itself only added because this phase
hadn't landed yet when Phase 18 ran) — re-bind to this phase's real
accessor now that it exists; (4) Phase 6's `title_provider` callback
(bound to `_conversation_display_title`, which reads
`self._conversation_id`/`self._messages` in its fallback path) — re-bind
to whatever now backs that lookup, with an integration assertion that
the rebound provider sees the migrated projection. Additionally, Phase
18's `on_activate` and `on_delete` presenter callbacks were bound to
`switch_conversation`/
`_confirm_delete_conversation` while those methods still lived on
`ChatSidebar` directly — since this phase moves both methods into its own
object, Phase 18's callback wiring needs re-pointing to their new
location too. **Each of these must be either rebound to this phase's new
owner or intentionally preserved through a stable delegator** — this
phase's own scope includes doing so, for the same reason as the round-6
resolution: it's `ChatSidebar`-side glue and already-extracted objects'
constructor arguments, not a reach into those objects' internals.

By the time this phase lands, every currently-known reader is migrated;
only the two remaining direct *mutators* — group L (not yet extracted,
Phase 24) and group M (not yet extracted, Phase 26) — still need the
facade's mutable interface. The same applies to
`_health`/`_loading_model`/`_load_failed`/`_model`/`_ollama_cli_busy`,
which `_send` (Phase 26) reads directly: those belong to interfaces
Phases 8/10/20 establish, consumed via callback the same way, not copied.

**Correction (round 8):** Phase 22 does not introduce the greeting reset
calls. Phase 10 already rewired `clear_chat`, successful `new_chat`, and
`switch_conversation` to `reset_greetings()` when it took ownership of
`_greeted_models`; this phase preserves those calls at the same branch
positions while moving the surrounding lifecycle methods. Likewise, the
Phase 6 title-provider rebind is not complete until its integration test
proves export title fallback reads this phase's projection.

**Correction (round 9):** this phase is also the explicit rebind point
for the Phase-12 replay, Phase-16 native-rendering, and Phase-20 CLI
message-ID providers, plus Phase 16's `current_text` provider. It re-points
Phase 18's `on_activate`/`on_delete` callbacks to the extracted lifecycle
owner and removes Phase 18's shorter-lived mark/rebuild window delegators
after a caller inventory proves group F was their last consumer. These
are required cutover steps, not follow-up cleanup.

**Correction (round 7) — message-ID allocation and `_history_restored`.**
`_next_msg_id`/`_msg_counter` (`window.py:2071-2073`) were previously
misassigned to the message-action phase; verified their five call sites
are actually `_apply_restored_transcript` (this phase, `window.py:2177`),
`_post_status_message` (Phase 20, `window.py:2903`), `_send` and
`_start_assistant_stream` (Phase 26, `window.py:3143,3450`), and
`_append_message` (Phase 16's native rendering, `window.py:3181`) — never
group L. This phase becomes the owner of message-ID allocation (it's
fundamentally about the identity of entries in the message stream this
phase now projects), preserving the exact `{prefix}-{counter}-{uuid
suffix}` format; `_next_msg_id` stays a plain, unchanged-signature method
consumers call the same way, with Phases 16/20/26's already-extracted
objects' calls re-pointed to the new owner as part of this phase's
rewiring work (same pattern as the reader migrations above). Separately,
`_history_restored` (`window.py:518,1613,1986,2132,2146,2158`) is written
repeatedly by this phase's own methods but confirmed **never read
anywhere in the file** — this phase must keep writing it into the
projection as-is; dropping it would be behavior-unrelated cleanup mixed
into a structural extraction, against the ground rules, even though nothing
currently consumes it.

Depends on Phase 12 (calls `transcript.reset(...)` without knowing the
backend) and still needs a narrow "cancel the active stream" hook back
into group M (`_invalidate_active_stream` call sites) taken as a
constructor callback. Risk: medium-high — real behavioral subtlety around
empty-conversation pruning and the persistence-failure-ordering asymmetry
(§2 group F), plus the new message-state interface and facade design.
Verification: full suite + Phase 21 tests passing unmodified, explicit
manual pass of delete/switch/new/clear sequences (including simulated
persistence failures) in both transcript modes (using Phase 11/15's
native tests for the native side), and confirmation that the
still-unmigrated group L/M code paths are provably unaffected (same call
sites, same behavior, reading through the facade).

**Phase 23 — Message-action characterization (test-only), including
`_on_web_intent` dispatch and completed replace/continue commits.**
`ChatSidebar`-level tests calling the real `_delete_message`/
`_regenerate_message`/`_edit_resend_message`/`_continue_message` methods
— `test_message_actions.py` today only tests the pure-function halves
(`join_continue`, etc.) and raw `ConversationStore` operations, never
these methods on a real `ChatSidebar`. Cover both transcript modes (using
Phase 11/15's tests as a template). Additionally, per group O's gap in
§6.2 ("Dispatch table itself (`_on_web_intent`) not directly asserted"),
add a direct test that feeds each intent type
(`copy_text`/`regenerate`/`continue`/`delete_message`/`edit_resend`)
through `_on_web_intent` and asserts it routes to the correct handler —
this is the dispatch table Phase 16's native adapter will also route
through, so it needs its own direct assertion, not just indirect coverage
via the handler tests. **Also required:** `test_generation_lifecycle.py`
contains zero references to `"replace"`/`"continue"` mode or
`_commit_assistant_result` (confirmed by direct search) — every existing
generation-lifecycle test is about cancellation/switch races, none of
them let a regenerate/edit-resend/continue actually *complete*. Merely
asserting that `_regenerate_message`/`_continue_message` start a stream
would leave `_commit_assistant_result`'s replace and continue branches
(`window.py:3674`) — which update `self._messages[idx]["content"]` and
persist via `store.update_message`/`store.append_message` differently per
mode — completely unprotected. Add tests that let a scripted fake
`chat_stream` run to completion after a regenerate/continue and assert
the final in-memory content and the persisted row match, for both
branches. Risk: n/a (test-only). Verification: new tests pass against
current `main` unmodified.

**Phase 24 — Message-action extraction (group L), native-rendering
methods excluded, message-ID allocation excluded, migrating onto Phase
22's message-state interface.** `_find_message_index`, `_api_messages`,
`_clipboard_set`, `_delete_message`, `_drop_messages_from`,
`_regenerate_message`, `_edit_resend_message`, `_continue_message` — the
mode-agnostic business logic only; `_native_action_bar`/`_native_edit_user`/
`_native_remove_message` already moved to Phases 12/16 (native rendering),
and `_next_msg_id`/`_msg_counter` belong to Phase 22 (conversation-lifecycle/
message-state), not this group — see Phase 22's round-7 correction. This
is where Phase 16's native `on_intent` callback and `_on_web_intent`'s
dispatch (for WebKit) both terminate. Per Phase 22's staged migration,
this phase is where group L stops reading/writing `self._messages`
through the compatibility facade and switches to calling its narrow
mutation interface directly — group M (Phase 26) is still on the facade
at this point, so the facade itself isn't removed yet, only group L's
dependency on it. Still calls into group M (`_start_assistant_stream`) to
actually run a regenerate/edit/continue — that call should go through a
narrow interface, not reach into streaming internals. Depends on Phase
23's tests, Phase 16's adapter, Phase 22's message-state interface. Risk:
medium-high. Verification: full suite + Phase 23 tests passing
unmodified.

**Correction (round 9):** this phase rebinds Phase 16's `on_intent`
provider to the extracted group-L owner. After both WebKit and native
dispatch terminate there, it inventories and removes the now-unused
window action/removal delegators; any transcript delegator still needed
by group M remains until Phase 26.

**Phase 25 — Streaming characterization (test-only), covering `_send`
itself, not only mid-stream errors.** `test_generation_lifecycle.py`
covers cancellation and generation races thoroughly but contains zero
references to `OllamaError` (confirmed by direct search) — the
non-cancellation error path (`finalize_ui`'s `err is not None` branch:
`classify_error` reclassifying health mid-stream, the error rendering
into the transcript, `_commit_assistant_result`'s `allow_empty=bool(err)`
path) has no deterministic test.

**Correction (round 7):** confirmed `test_generation_lifecycle.py`'s own
`start_stream` helper docstring states it exists to "Mirror what `_send()`
does, minus composer/health/model UI guards"
(`scripts/test_generation_lifecycle.py:148`) — meaning `_send` itself has
**zero** direct coverage, not merely thin coverage. Before Phase 26 moves
it, this phase must characterize: the empty-input guard (nothing sent for
blank/whitespace-only text), the busy guards (`_streaming`/
`_loading_model`/CLI-busy all blocking send), composer-command routing
(`_try_composer_command` intercepting `ollama pull/list/ps` before
anything reaches the model), the unhealthy-reprobe branch
(`not self._health.can_chat` triggering `_refresh_models()` instead of
sending), the missing-model guard (`not self._model` no-op), and the
successful path's exact append/persist/start sequence (user message
appended to in-memory state, persisted, composer hint synced, stream
started — in that order). Risk: n/a (test-only). Verification: new tests
pass against current `main` unmodified.

**Phase 26 — Streaming-engine extraction (group M), last, migrating onto
Phase 22's message-state interface and retiring its facade.** `_send`,
`_start_assistant_stream`, `_commit_assistant_result`, `_stream_finished`,
`_request_stop`, `_invalidate_active_stream`, `_scroll_to_end` — the most
entangled group in the file (§4.1, §4.3, §5 risks 2-4), and the largest
single method in the class (`_start_assistant_stream`, ~250 lines).
`_send` alone touches nearly every other extracted interface directly: it
calls `_try_composer_command` (Phase 20), reads `self._health.can_chat`
and calls `_refresh_models`-equivalent behavior on failure (Phase 8),
checks model-session state (Phase 10, per the round-5 ownership
correction), posts into the transcript (Phases 12/14/16), appends to and
persists through the conversation/message state (Phases 22/24), and
updates status/title (Phase 18) — see the dependency-table note below on
why this isn't listed as an exhaustive call-target list. Should only be
attempted after Phases 12-16, 22, 24 exist (and in practice 8, 10, 20,
since `_send` calls into all of them). Must preserve the generation-counter
by-value-capture pattern exactly (§4.3), preserve `_send`'s exact guard
ordering characterized in Phase 25, and finish migrating group M itself
onto Phase 22's message-state interface, Phase 10's model-session
interface, and Phase 20's CLI-busy interface — reading through their
query methods, not raw attributes.

**Correction (round 9):** Phase 20 already converted `_send` to the
permanent CLI `is_busy()`/`try_command()` interface, so this phase
preserves those calls. It also consumes the Phase-12/14/16 transcript
owner and Phase-18 sidebar/title interfaces directly. After group M is
migrated, a whole-file inventory gates removal of the last transcript,
sidebar/title, and model-session compatibility delegators/properties as
well as the Phase-22 messages facade; compatibility is removed only when
that inventory proves zero callers.

**Correction (round 6):** round 5 assigned this phase an "inventory and
migrate every remaining reader" step, on the theory that readers were
scattered across earlier phases and nobody else would touch them. Per
Phase 22's round-6/7 corrections, that's no longer the plan — Phase 22
itself migrates every currently-known read-only consumer (both the
`ChatSidebar`-retained presentation methods and the callback wiring it
supplies to already-extracted objects) at the point it introduces the
projection, precisely so that streaming extraction doesn't have to reach
back into earlier phases' controllers or unrelated presentation code. By
the time this phase runs, the only remaining raw consumers of `_messages`
are group L (already migrated in Phase 24) and group M (migrating right
here) — so this phase's facade removal is what round 4 originally
claimed, now actually true: once group M migrates onto Phase 22's
interface, the facade has zero remaining consumers and comes out clean.
Per the firm rule at the top of this section, this phase does not touch
the sensitivity state-machine issue (§5 risk 3). Risk: high. Verification:
full suite + Phase 25 tests passing unmodified, with particular attention
to `test_generation_lifecycle.py` passing unmodified (the strongest
existing regression guard for this group).

**A note on "Depends on," since Phase 26 makes the limits of that column
obvious:** the phase table's "Depends on" column lists hard ordering/
interface prerequisites — phases whose interface this phase's design
requires to exist first — not an exhaustive list of every collaborator a
phase's code happens to call. `_send` alone touches the interfaces from
roughly seven other phases; listing all of them for every phase that
calls widely (Phase 20, Phase 26 especially) would make the column noise
rather than signal. Where a specific omission changes what the phase
needs to be designed around (e.g. Phase 20 needing an `on_pull_succeeded`
hook into Phase 8's territory), that's called out in the phase's own
prose, as above, rather than left implicit in the table. **See
`REFACTOR_PLAN.md`'s ownership/migration matrix for a structured,
mechanically-checkable view of every shared-state row this note and the
corrections above describe in prose** — added in round 7 specifically
because prose alone had, by this round, missed the same class of
cross-phase detail six times running.

Each phase above assumes: the full 15-script suite runs genuinely
(Meson-backed tests actually executing — confirmed reproducible in this
environment: all 15 pass against `main`@`d12bf2e`, including
`test_installed_layout.py` 47/47 and `test_desktop_integration.py` 37/37
with zero skips) on the PR head, and CI is green on that exact head
before merge is even discussed. Scott may choose, at approval time, to
merge a test-only phase and its immediately-following extraction phase
into a single reviewed PR where the combined diff is still small and
single-purpose (e.g. Phase 1+2, both negligible risk) — that's a call
about PR packaging, not about whether the test must exist first, which
is not negotiable per the working rules.

---

## 8. What this audit does not decide

- Whether `ChatSidebar` extractions become plain modules, mixins, or
  composed controller objects — that's an implementation-design decision
  for whichever phase is actually approved, not something to fix in
  advance across all 26 phases.
- Whether the sensitivity state-machine (§5 risk 3) or the
  `_on_ollama_probe` generation-guard gap (§4.3) should ever be *fixed*
  (behavior-preserving consolidation), and if so when. Every extraction
  phase above preserves both exactly as they are today — that part is not
  optional (see the firm rule at the top of §7). Whether to fix either one
  *at all*, as a wholly separate and explicitly authorized PR after the
  relevant extraction lands, is Scott's call and is not resolved here.
- Any timeline or phase-count commitment beyond "small, bounded,
  independently reviewable, one responsibility at a time."

See `../REFACTOR_PLAN.md` for how Scott wants to sequence and gate this.
