# Stage 3 -- Factual summaries (derived only from generated evidence)

## 1. ChatSidebar method count and size distribution

- Total methods (top-level, direct children of `class ChatSidebar`): **99**
- Method body line-count: min=2, max=396, mean=31.8, median=18

| line-count bucket | method count |
|---|---|
| 1-5 | 14 |
| 6-15 | 28 |
| 16-30 | 28 |
| 31-60 | 17 |
| 61-120 | 10 |
| >120 | 2 |

Largest methods by body line-count:

- `_build_ui` -- 396 lines
- `_start_assistant_stream` -- 253 lines
- `_native_action_bar` -- 108 lines
- `_build_history_sidebar` -- 92 lines
- `__init__` -- 89 lines
- `_rebuild_history_list` -- 87 lines
- `_run_ollama_pull` -- 81 lines
- `_append_message` -- 80 lines
- `export_conversation` -- 71 lines
- `_on_model_load_finished` -- 68 lines

## 2. Complete attribute inventory

- Unique `self.X` attribute names encountered (includes true instance-data attributes AND `self.<method_name>` references, see attributes.tsv methodology note): **184**
- Total attribute occurrence rows: **1105**

Occurrences by AST context:

| context | occurrence rows |
|---|---|
| Load | 588 |
| mutation-call | 322 |
| Store | 133 |
| AnnAssign | 46 |
| getattr | 8 |
| AugAssign | 4 |
| Subscript-Store | 4 |

Attribute classification (from attribute-init-classification.tsv):

| classification | attribute count |
|---|---|
| never_written_only_read_or_called | 116 |
| initialized_in___init__ | 59 |
| first_assigned_elsewhere | 9 |

## 3. Exact cross-method call relationships (internal-calls.tsv)

- Total recorded internal call sites: **232**
- Distinct (caller, callee) pairs: **193**

Highest fan-out (methods that call the most *distinct* other ChatSidebar methods):

- `_build_ui` calls 14 distinct methods
- `switch_conversation` calls 10 distinct methods
- `new_chat` calls 9 distinct methods
- `_start_assistant_stream` calls 9 distinct methods
- `clear_chat` calls 8 distinct methods
- `_run_ollama_pull` calls 7 distinct methods
- `_send` calls 7 distinct methods
- `_edit_resend_message` calls 6 distinct methods
- `_on_ollama_probe` calls 6 distinct methods
- `_on_model_load_finished` calls 6 distinct methods

Highest fan-in (methods called from the most distinct call sites):

- `_set_status` -- called from 17 call sites
- `_append_message` -- called from 10 call sites
- `_native_remove_message` -- called from 8 call sites
- `_mark_history_dirty` -- called from 7 call sites
- `_refresh_chat_title` -- called from 6 call sites
- `_sync_composer_hint` -- called from 6 call sites
- `_find_message_index` -- called from 6 call sites
- `_apply_health` -- called from 6 call sites
- `_refresh_models` -- called from 5 call sites
- `_show_empty_state` -- called from 5 call sites

## 4. Callback / thread boundaries (callbacks.tsv)

- Total registered callback relationships: **55**

| mechanism | count |
|---|---|
| connect | 33 |
| GLib.idle_add | 14 |
| threading.Thread | 5 |
| GLib.timeout_add | 3 |

## 5. Exact ConversationStore / client / web calls (external-calls.tsv)

- Total recorded external call/construct sites: **63**

**ConversationStore(...)** (1 call sites):

- `__init__/construct` x1

**self._store** (37 call sites):

- `delete_message` x5
- `get_conversation` x4
- `create_conversation` x3
- `list_messages` x3
- `append_message` x3
- `update_message` x3
- `is_empty` x2
- `prune_empty_conversations` x2
- `delete_conversation` x2
- `get_active_conversation` x2
- `clear_messages` x1
- `list_conversations` x1
- `export_dict` x1
- `export_markdown` x1
- `set_active` x1
- `ensure_active` x1
- `touch` x1
- `set_model` x1

**self._web** (19 call sites):

- `post` x16
- `reset` x3

**self.client** (6 call sites):

- `is_model_loaded` x1
- `load_model` x1
- `pull_model` x1
- `format_list_models` x1
- `format_ps_models` x1
- `chat_stream` x1

## 6. Runtime-observed method coverage by script

See test-evidence.md for the full per-script breakdown and the summary table. Headline (computed from runtime-method-entries.tsv): **53/99** ChatSidebar methods (53.5%) were observed executing in at least one of the 15 test scripts in this run; **46/99** had no execution evidence in this run (static reachability aside -- see test-evidence.md, this is NOT a claim they are dead code). Exactly **5** of the 15 scripts produce any ChatSidebar method entry: test_generation_lifecycle, test_markdown_sanitization, test_restore_scroll, test_sidebar_interactions, test_wire_code_ui_batch. The other 10 (including test_message_actions, which imports only module-level helpers, never the class) show zero entries as a fact about their scope.

## 7. Branch-level limitations method-entry tracing cannot answer

- Method entry tracing (sys.settrace on 'call' events) proves a method's frame was entered at least once; it records neither which `if`/`else`/`except` branches executed inside that method, nor how many times per entry, nor argument values.
- A method observed with entry_count=N in runtime-method-entries.tsv was entered N times in that script's run; this says nothing about whether every early-return or exception path in its body was exercised.
- Callback bodies registered via `.connect(...)`, `GLib.idle_add`, `GLib.timeout_add`, or `threading.Thread(target=...)` (see callbacks.tsv, which is a PATTERN-MATCHED registration inventory -- see its scope note in extract.py; it excludes GTK async APIs like `Gtk.FileDialog.save`, the constructor-injected `WebTranscriptView(on_intent=...)` bridge, and does not resolve helper-forwarded `handler` callbacks) only execute if the corresponding GTK signal actually fires, the GLib main loop iterates enough times, or the worker thread is joined/awaited by the test -- absence of entry for such a method may reflect a timing/pump issue in this run rather than the code path being unreachable.
- Method-entry counts are TIMING-SENSITIVE for GLib-layout callbacks (the five composer-layout methods) -- across independent runs the observed method SET and the coverage union are stable but some entry_count integers vary; coverage conclusions key off the method set, not counts.
- Tracing (`sys.settrace` + `threading.settrace`) covers this process's main thread and Python `threading` threads; it does NOT cover separate OS subprocesses. **Three** of the 15 scripts spawn `subprocess`-based children: `test_dependency_declaration.py` (repeatedly runs `check_dependencies.py`), `test_installed_layout.py`, and `test_desktop_integration.py` (both run `meson setup`/`ninja install`, and desktop-integration additionally spawns a CHILD run of the installed-layout test). Those children are untraced. Note `compileall.compile_dir` inside `test_installed_layout.py` runs IN-PROCESS (not a subprocess), so it would in principle be traceable -- but that script never imports `window.ChatSidebar` anyway. None of these three scripts constructs a ChatSidebar in-process OR in a child, so the observed 53/99 method set is unaffected by the untraced children.

