# test-evidence.md

Generated from methods.tsv, internal-calls.tsv, runtime-method-entries.tsv, direct-test-calls.tsv. See gen/test_evidence.py docstring for exact category rules.

**Caveat (applies to every 'Directly invoked' and 'Runtime-observed indirectly' row below):** method entry was observed via sys.settrace/threading.settrace; this proves the method's body started executing at least once in this run of this script. It does NOT prove which internal branches, early returns, or exception paths within that method executed. No claim of full branch coverage is made anywhere in this document.

## test_dependency_declaration

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_desktop_integration

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_generation_lifecycle

- Directly invoked by test code AND executed at runtime: 4
- Runtime-observed indirectly: 45
- Statically reachable but not runtime-observed: 38
- No execution evidence in this run: 12
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)

**Directly invoked and executed:** _persist_message, _request_stop, _start_assistant_stream, switch_conversation

**Runtime-observed indirectly (alphabetical, first 30; full set in runtime-method-entries.tsv -- entry counts are timing-sensitive so no count-ranking is asserted):** __init__, _api_messages, _apply_composer_height, _apply_health, _begin_model_load, _build_history_sidebar, _build_load_overlay, _build_ui, _commit_assistant_result, _composer_content_height_px, _composer_hint_should_show, _composer_line_height_px, _composer_max_visible_lines, _ensure_conversation, _find_message_index, _hide_load_overlay, _hook_composer_surface_layout, _install_css, _invalidate_active_stream, _make_chat_actions_popover, _mark_history_dirty, _next_msg_id, _on_load_chunk, _on_load_status, _on_model_load_finished, _on_model_selected, _on_ollama_probe, _on_web_intent, _preferred_model, _rebuild_history_list ...

**Statically reachable, not observed this run:** _active_chat_is_empty, _append_message, _apply_restored_transcript, _brand_icon_path, _clipboard_set, _composer_cmd_busy, _confirm_delete_conversation, _continue_message, _conversation_display_title, _delete_message, _drop_messages_from, _edit_resend_message, _format_pull_progress, _make_empty_brand_icon, _native_action_bar, _native_edit_user, _native_remove_message, _post_status_message, _regenerate_message, _remove_empty_state, _run_ollama_info, _run_ollama_pull, _safe_export_basename, _scroll_to_end, _select_active_history_row, _send, _set_composer_cmd_busy, _show_empty_state, _try_composer_command, _update_status_message ...


## test_installed_layout

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_markdown_sanitization

- Directly invoked by test code AND executed at runtime: 3
- Runtime-observed indirectly: 44
- Statically reachable but not runtime-observed: 40
- No execution evidence in this run: 12
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)

**Directly invoked and executed:** _persist_message, _start_assistant_stream, switch_conversation

**Runtime-observed indirectly (alphabetical, first 30; full set in runtime-method-entries.tsv -- entry counts are timing-sensitive so no count-ranking is asserted):** __init__, _api_messages, _apply_composer_height, _apply_health, _apply_restored_transcript, _begin_model_load, _build_history_sidebar, _build_load_overlay, _build_ui, _commit_assistant_result, _composer_content_height_px, _composer_hint_should_show, _composer_line_height_px, _composer_max_visible_lines, _ensure_conversation, _find_message_index, _hide_load_overlay, _hook_composer_surface_layout, _install_css, _make_chat_actions_popover, _mark_history_dirty, _next_msg_id, _on_load_chunk, _on_load_status, _on_model_load_finished, _on_model_selected, _on_ollama_probe, _on_web_intent, _preferred_model, _rebuild_history_list ...

**Statically reachable, not observed this run:** _active_chat_is_empty, _append_message, _brand_icon_path, _clipboard_set, _composer_cmd_busy, _confirm_delete_conversation, _continue_message, _conversation_display_title, _delete_message, _drop_messages_from, _edit_resend_message, _format_pull_progress, _invalidate_active_stream, _make_empty_brand_icon, _native_action_bar, _native_edit_user, _native_remove_message, _post_status_message, _regenerate_message, _remove_empty_state, _render_empty_transcript, _request_stop, _run_ollama_info, _run_ollama_pull, _safe_export_basename, _scroll_to_end, _select_active_history_row, _send, _set_composer_cmd_busy, _show_empty_state ...


## test_message_actions

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_multichat

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_ollama_health

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_release_identity

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_restore_scroll

- Directly invoked by test code AND executed at runtime: 1
- Runtime-observed indirectly: 39
- Statically reachable but not runtime-observed: 47
- No execution evidence in this run: 12
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)

**Directly invoked and executed:** switch_conversation

**Runtime-observed indirectly (alphabetical, first 30; full set in runtime-method-entries.tsv -- entry counts are timing-sensitive so no count-ranking is asserted):** __init__, _apply_composer_height, _apply_health, _apply_restored_transcript, _begin_model_load, _build_history_sidebar, _build_load_overlay, _build_ui, _composer_content_height_px, _composer_hint_should_show, _composer_line_height_px, _composer_max_visible_lines, _ensure_conversation, _hide_load_overlay, _hook_composer_surface_layout, _install_css, _make_chat_actions_popover, _mark_history_dirty, _on_load_chunk, _on_load_status, _on_model_load_finished, _on_model_selected, _on_ollama_probe, _on_web_intent, _preferred_model, _rebuild_history_list, _refresh_chat_title, _refresh_models, _restore_history, _select_model_name ...

**Statically reachable, not observed this run:** _active_chat_is_empty, _api_messages, _append_message, _brand_icon_path, _clipboard_set, _commit_assistant_result, _composer_cmd_busy, _confirm_delete_conversation, _continue_message, _conversation_display_title, _delete_message, _drop_messages_from, _edit_resend_message, _find_message_index, _format_pull_progress, _invalidate_active_stream, _make_empty_brand_icon, _native_action_bar, _native_edit_user, _native_remove_message, _next_msg_id, _persist_message, _post_status_message, _regenerate_message, _remove_empty_state, _render_empty_transcript, _request_stop, _run_ollama_info, _run_ollama_pull, _safe_export_basename ...


## test_sidebar_interactions

- Directly invoked by test code AND executed at runtime: 3
- Runtime-observed indirectly: 38
- Statically reachable but not runtime-observed: 47
- No execution evidence in this run: 11
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)

**Directly invoked and executed:** _rebuild_history_list, _refresh_models, toggle_sidebar

**Runtime-observed indirectly (alphabetical, first 30; full set in runtime-method-entries.tsv -- entry counts are timing-sensitive so no count-ranking is asserted):** __init__, _apply_composer_height, _apply_health, _apply_restored_transcript, _begin_model_load, _build_history_sidebar, _build_load_overlay, _build_ui, _composer_content_height_px, _composer_hint_should_show, _composer_line_height_px, _composer_max_visible_lines, _ensure_conversation, _hide_load_overlay, _hook_composer_surface_layout, _install_css, _make_chat_actions_popover, _mark_history_dirty, _on_load_chunk, _on_load_status, _on_model_load_finished, _on_model_selected, _on_ollama_probe, _on_sidebar_toggled, _on_web_intent, _preferred_model, _refresh_chat_title, _restore_history, _select_active_history_row, _set_load_controls_sensitive ...

**Statically reachable, not observed this run:** _active_chat_is_empty, _api_messages, _append_message, _brand_icon_path, _clipboard_set, _commit_assistant_result, _composer_cmd_busy, _confirm_delete_conversation, _continue_message, _conversation_display_title, _delete_message, _drop_messages_from, _edit_resend_message, _find_message_index, _format_pull_progress, _invalidate_active_stream, _make_empty_brand_icon, _native_action_bar, _native_edit_user, _native_remove_message, _next_msg_id, _persist_message, _post_status_message, _regenerate_message, _remove_empty_state, _render_empty_transcript, _request_stop, _run_ollama_info, _run_ollama_pull, _safe_export_basename ...


## test_stream_cancellation

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_web_content_security_policy

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_web_navigation_policy

- Directly invoked by test code AND executed at runtime: 0
- Runtime-observed indirectly: 0
- Statically reachable but not runtime-observed: 0
- No execution evidence in this run: 99
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)


## test_wire_code_ui_batch

- Directly invoked by test code AND executed at runtime: 1
- Runtime-observed indirectly: 39
- Statically reachable but not runtime-observed: 47
- No execution evidence in this run: 12
- Syntactically directly-called in test source but NOT observed executing (syntactic evidence only, not execution): 0
- (Total ChatSidebar methods: 99)

**Directly invoked and executed:** switch_conversation

**Runtime-observed indirectly (alphabetical, first 30; full set in runtime-method-entries.tsv -- entry counts are timing-sensitive so no count-ranking is asserted):** __init__, _apply_composer_height, _apply_health, _apply_restored_transcript, _begin_model_load, _build_history_sidebar, _build_load_overlay, _build_ui, _composer_content_height_px, _composer_hint_should_show, _composer_line_height_px, _composer_max_visible_lines, _ensure_conversation, _hide_load_overlay, _hook_composer_surface_layout, _install_css, _make_chat_actions_popover, _mark_history_dirty, _on_load_chunk, _on_load_status, _on_model_load_finished, _on_model_selected, _on_ollama_probe, _on_web_intent, _preferred_model, _rebuild_history_list, _refresh_chat_title, _refresh_models, _restore_history, _select_model_name ...

**Statically reachable, not observed this run:** _active_chat_is_empty, _api_messages, _append_message, _brand_icon_path, _clipboard_set, _commit_assistant_result, _composer_cmd_busy, _confirm_delete_conversation, _continue_message, _conversation_display_title, _delete_message, _drop_messages_from, _edit_resend_message, _find_message_index, _format_pull_progress, _invalidate_active_stream, _make_empty_brand_icon, _native_action_bar, _native_edit_user, _native_remove_message, _next_msg_id, _persist_message, _post_status_message, _regenerate_message, _remove_empty_state, _render_empty_transcript, _request_stop, _run_ollama_info, _run_ollama_pull, _safe_export_basename ...


## Summary table

| script | directly invoked & executed | runtime-observed indirectly | statically reachable, not observed | no execution evidence |
|---|---|---|---|---|
| test_dependency_declaration | 0 | 0 | 0 | 99 |
| test_desktop_integration | 0 | 0 | 0 | 99 |
| test_generation_lifecycle | 4 | 45 | 38 | 12 |
| test_installed_layout | 0 | 0 | 0 | 99 |
| test_markdown_sanitization | 3 | 44 | 40 | 12 |
| test_message_actions | 0 | 0 | 0 | 99 |
| test_multichat | 0 | 0 | 0 | 99 |
| test_ollama_health | 0 | 0 | 0 | 99 |
| test_release_identity | 0 | 0 | 0 | 99 |
| test_restore_scroll | 1 | 39 | 47 | 12 |
| test_sidebar_interactions | 3 | 38 | 47 | 11 |
| test_stream_cancellation | 0 | 0 | 0 | 99 |
| test_web_content_security_policy | 0 | 0 | 0 | 99 |
| test_web_navigation_policy | 0 | 0 | 0 | 99 |
| test_wire_code_ui_batch | 1 | 39 | 47 | 12 |

## Scripts with zero ChatSidebar involvement

The following scripts produce zero ChatSidebar method entries and zero syntactic direct ChatSidebar calls (they test other modules/behaviors: dependency checking, installed-layout/meson, release identity, WebKit CSP/navigation policy via a bare WebView, ConversationStore directly, or the ollama_health module). Nine never import `window.ChatSidebar`; the tenth, `test_message_actions`, imports only module-level helper functions from `window` and never constructs the class. Zero ChatSidebar entries here is a fact about the script's scope, not a tracer gap:

- test_dependency_declaration
- test_desktop_integration
- test_installed_layout
- test_message_actions
- test_multichat
- test_ollama_health
- test_release_identity
- test_stream_cancellation
- test_web_content_security_policy
- test_web_navigation_policy

## Union across all 15 scripts

- Methods with RUNTIME execution evidence (entered per runtime-method-entries.tsv) in AT LEAST ONE of the 15 scripts: **53 / 99**
- Methods syntactically directly-invoked in test source (direct-test-calls.tsv, receiver_class==ChatSidebar) across all scripts: 7 (all of which were also traced this run; syntactically-direct-but-not-traced: none)
- Methods with NO runtime execution evidence in ANY of the 15 scripts this run: **46 / 99**

Methods never observed executing in this run (may still be statically reachable, may be UI-callback-only paths not exercised by the current scripted interactions, or may be genuinely dead/unreachable from tested entry points -- this run does not distinguish those cases):

- _active_chat_is_empty
- _append_message
- _brand_icon_path
- _clipboard_set
- _composer_cmd_busy
- _confirm_delete_conversation
- _continue_message
- _conversation_display_title
- _delete_message
- _drop_messages_from
- _edit_resend_message
- _format_pull_progress
- _handle_close_request
- _make_empty_brand_icon
- _native_action_bar
- _native_edit_user
- _native_remove_message
- _on_buffer_changed
- _on_composer_insert_text
- _on_health_action
- _on_history_row_activated
- _on_input_key
- _on_key
- _post_status_message
- _regenerate_message
- _remove_empty_state
- _run_ollama_info
- _run_ollama_pull
- _safe_export_basename
- _scroll_to_end
- _send
- _set_composer_cmd_busy
- _show_empty_state
- _sync_empty_brand_icon
- _try_composer_command
- _update_composer_char_counter
- _update_status_message
- clear_chat
- delete_conversation
- export_conversation
- hide_to_tray
- new_chat
- open_settings
- set_close_handler
- toggle
- toggle_maximize

