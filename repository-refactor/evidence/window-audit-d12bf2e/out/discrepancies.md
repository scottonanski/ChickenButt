# discrepancies.md

Comparison of `repository-refactor/research/00-window-audit.md` and
`repository-refactor/REFACTOR_PLAN.md` against the Stage 1-3 source-derived
evidence generated in this evidence directory. Per the assignment, this is
NOT a full line-by-line audit of all 1,543 + 371 lines of those documents —
it targets the mechanically checkable factual claims (line numbers, method
counts, "never called"/"never read" assertions, attribute ownership) that
the generated TSVs can directly confirm or contradict. Neither draft
document was modified. Ownership proposals, phase structure, and the
extraction plan itself are explicitly out of scope for this comparison, per
the assignment's instruction not to treat those as ground truth in either
direction.

**Revision note:** this file was revised after an independent review
(Codex) of the first evidence pass. That review's defects 7, 8, and 10
directly concern this document: the `_messages` "one method short" item was
withdrawn as a discrepancy (it was never one), the `_preferred_model` item
was rewritten to stop resting on method-entry alone, and a genuine
`_transcript_mode` discrepancy the first pass missed was added.

---

## DISCREPANCY 1. Class line-range: internally inconsistent

**Existing claim** (`00-window-audit.md:8-10`):
> "File is 3,753 lines; the module holds a handful of top-level
> helpers/constants (lines 1-494) and a single class, `ChatSidebar`
> (`Adw.ApplicationWindow` subclass, lines 495-3753, 99 methods)."

**Source-derived result:** The `ChatSidebar` class body (per
`ast.ClassDef.end_lineno`) ends at line **3742**, not 3753. Lines
3743-3753 are a module-level function, `_fmt_bytes`, defined *after* the
class, at module scope — confirmed by the extractor's tooling output
(`ChatSidebar class: lines 495-3742`) and by direct inspection: line 3745
is `def _fmt_bytes(n: float | int) -> str:` at zero indentation (not a
class member).

**Evidence:** `out/methods.tsv` (99 methods, last method `_stream_finished`
end_line=3742); extractor stdout `ChatSidebar class: lines 495-3742`;
`window.py:3745` (`def _fmt_bytes`, column 0).

**Classification:** internally inconsistent. The same document's own §2
"Group A" list (line 290) correctly places `_fmt_bytes` at line 3745 as a
**module-level helper, not a ChatSidebar method**. The intro's "lines
495-3753" range for the class contradicts the document's own later, correct
treatment of `_fmt_bytes` as outside the class. The class actually ends at
3742; the method count (99) is otherwise correct (confirmed exactly by
`methods.tsv`).

---

## DISCREPANCY 2. `_transcript_mode` described as "fixed once ... never changes at runtime" — contradicted by source

**Existing claim** (`00-window-audit.md:495-496`):
> "`_transcript_mode` is fixed once (module env var `CHICKENBUTT_TRANSCRIPT`
> read at `__init__`, `window.py:509`) and never changes at runtime."

**Source-derived result:** `_transcript_mode` is assigned in **two**
distinct methods, not one: `__init__` at `window.py:509`
(`self._transcript_mode = _transcript_mode()`, from the env var) **and**
`_build_ui` at `window.py:805` (`self._transcript_mode = "native"`), inside
the `except` branch that runs when `WebTranscriptView(...)` construction
fails and the code falls back to the native GTK transcript. So the value
can change from `"webkit"` to `"native"` after `__init__` has already set
it.

**Evidence:** `out/attributes.tsv` rows for `_transcript_mode` — two
`Store` contexts: `__init__:509` and `_build_ui:805`
(`self._transcript_mode = "native"`), plus many `Load` rows. Source:
`window.py:805` inside `_build_ui`'s WebKit-construction `except` block.

**Classification:** incorrect as literally worded, though the intent is
nearly right. The value IS stable *after UI construction finishes* (nothing
rewrites it at true runtime — during send/switch/stream), and it IS
effectively a single logical decision. But "fixed once ... at `__init__`"
and "never changes" are both false in the specific sense that the
`__init__` assignment can be overwritten during `_build_ui` when WebKit is
unavailable. A refactor that treated the `__init__` write as the sole
authority (e.g. snapshotting mode at construction and passing it down)
would silently drop the native-fallback path. Worth flagging precisely
because the draft uses this claim to justify branching decisions.

---

## NON-DISCREPANCY (withdrawn) — `_preferred_model` coverage

The first evidence pass listed `_preferred_model` as a discrepancy, on the
grounds that the draft calls it "completely untested" while runtime tracing
shows it executing. That framing was itself imprecise and is **withdrawn**;
here is the accurate picture.

**Existing claim** (`00-window-audit.md`, round-7 correction to §7 Phase 7,
~line 836):
> "`_preferred_model` (`window.py:2547`) and the model-selection edge cases
> in `_select_model_name`/`_on_model_selected`... are equally untested."

**Source + test-inspection result:**
- `_preferred_model` **does execute** at runtime in all 5 GUI scripts
  (`runtime-method-entries.tsv`), reached via `_on_ollama_probe`
  (`internal-calls.tsv`: `_on_ollama_probe -> _preferred_model`,
  `window.py:2438`). Method entry alone, however, proves only that the frame
  ran — NOT that any assertion targeted its behavior.
- There IS limited **indirect outcome coverage**:
  `test_sidebar_interactions.py:237-242` drives `_refresh_models()` and then
  asserts `win._model == "fake-model-a"` — the end result of the
  probe → selection chain that `_preferred_model` participates in.
- That assertion does **not** target `_preferred_model`'s own decision
  logic — its precedence between a conversation's stored model, the
  last-used model, and the probe's model list. No test exercises those
  branches directly.

**Classification:** the draft's wording ("completely untested", "zero
references") is too strong — there is incidental execution plus a single
indirect outcome assertion — but the draft's underlying point (no test
targets `_preferred_model`'s precedence logic) is essentially correct. Best
described as **imprecise wording, substantively defensible**, NOT a factual
contradiction. Method-entry evidence is explicitly insufficient to call it
"tested"; this evidence set cannot establish assertion/branch coverage
either way. (The neighboring `_on_health_action` half of the draft's
sentence IS fully confirmed as uncovered — see confirmed-correct list
below.)

---

## Confirmed-correct claims (spot-checked, not discrepancies)

Listed because they were specifically checked against generated evidence
and found to match exactly:

- `_history_restored` is write-only: all 6 occurrences in
  `attributes.tsv` are `Store` context (`__init__:518`, `new_chat:1613`,
  `switch_conversation:1986`, `_restore_history:2132,2146,2158`); zero
  `Load` rows exist for this attribute. Matches the claim exactly.
- `_greeted_models` ownership: cleared (mutation-call `.clear()`) in
  exactly `clear_chat` (1543), `new_chat` (1611), `switch_conversation`
  (1970) — all group F — and read+mutated only in
  `_on_model_load_finished` (2837 Load, 2838 mutation-call `.add()`).
  Matches the claim exactly, including all cited line numbers.
- `_next_msg_id` call sites: exactly 5, at the exact cited lines —
  `_apply_restored_transcript:2177`, `_post_status_message:2903`,
  `_send:3143`, `_start_assistant_stream:3450`, `_append_message:3181`.
  Matches the claim exactly.
- `_on_health_action`'s three branches have zero execution evidence in
  this run and zero internal ChatSidebar callers (`internal-calls.tsv` has
  no row with it as callee; its only registration is a GTK `clicked`
  handler, `callbacks.tsv`: `_build_ui`, `window.py:784`, that no script's
  scripted interaction triggers). Matches the "completely untested" claim.
- The `_messages` in-memory-projection mutator set named in §5 risk 4 —
  `clear_chat`, `new_chat`, `switch_conversation`, `_restore_history`
  (group F); `_delete_message`, `_drop_messages_from`, `_regenerate_message`,
  `_edit_resend_message` (group L); `_send`, `_commit_assistant_result`
  (group M) — is **exactly correct** as the set of methods that mutate an
  *existing* conversation's in-memory list. `attributes.tsv` also shows an
  eleventh write site, `__init__` (`window.py:501`), but that is
  fresh-instance initialization of an empty list, not a mutation of an
  existing projection — so its omission from the draft's F/L/M "ten
  methods" count is correct, not an error. (The first evidence pass wrongly
  flagged this as "one method short"; that finding is **withdrawn**.)
- Native transcript-rendering methods (`_append_message`,
  `_native_action_bar`, `_native_edit_user`, `_native_remove_message`)
  have zero runtime entries across all 15 scripts in this run (all
  ChatSidebar-constructing scripts default to webkit mode). Matches the
  "Group N — None" coverage claim exactly.
- The 15-script suite passed 15/15 (exit code 0 for every script) when
  re-run independently, twice, in this session, corroborating the "run
  once, 15/15 passing" baseline claim in `REFACTOR_PLAN.md:18`.
- Total method count (99) and the `__init__`-attribute count (59 assigned
  directly in `__init__`) both match `00-window-audit.md`'s stated figures
  exactly (`methods.tsv` count = 99;
  `attribute-init-classification.tsv` `initialized_in___init__` count =
  59).

---

## Scope note / limitation

This comparison covered: the class line-range claim, the `_transcript_mode`
"fixed once" claim, the state inventory in §3 (`_history_restored`,
`_greeted_models`, `_messages`, `_msg_counter`/`_next_msg_id`), the §6.2
coverage-gap claims about groups I and N specifically, and the
`REFACTOR_PLAN.md` baseline-run claim. It did **not** exhaustively
re-derive every line number, call-site claim, or "N methods" count in every
one of the 26 phases, the full §4.1 cross-group call graph, or the
ownership/migration matrix — those would require a follow-up pass targeting
specific sections Codex flags as needing verification. Per the assignment,
no ownership/phase judgment is offered here regardless. Note also that
"coverage" claims in the draft are about *assertion/branch* coverage, which
this evidence set (method-entry tracing + syntactic call search) cannot
establish; confirmations above about "untested" methods rest on the
stronger, decidable facts (no caller, no runtime entry, no direct test
call), not on method-entry counts.
