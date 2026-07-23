#!/usr/bin/env python3
"""
Runtime method-entry tracer for ChatSidebar, run per test script without
modifying any repository file.

Usage: python3 run_traced.py <window.py path> <target test script> <out json path>

Method: installs a Python-level sys.settrace / threading.settrace hook that
records, for every function 'call' event whose code object's co_filename is
window.py and whose first bound local is named 'self' with
type(self).__name__ == 'ChatSidebar', the method name, a running entry
count, and the def's source line (co_firstlineno).

Caveats disclosed here and repeated in test-evidence.md:
  - sys.settrace/threading.settrace only cover the current OS process and
    Python threads created via the `threading` module in that process
    (threading.settrace propagates the trace function to threads started
    after the call). Any separate OS subprocess (e.g. a `meson install`
    child process, or a `subprocess.run(...)` call) is NOT traced -- such
    children are reported separately as "untraced child process" in
    test-evidence.md when detected.
  - Ten of the 15 test scripts show zero ChatSidebar method entries, so
    exactly FIVE scripts exercise ChatSidebar at runtime
    (test_generation_lifecycle, test_markdown_sanitization,
    test_restore_scroll, test_sidebar_interactions, test_wire_code_ui_batch).
    Of the ten zero-entry scripts, nine never import window.ChatSidebar at
    all (test_dependency_declaration, test_desktop_integration,
    test_installed_layout, test_multichat, test_ollama_health,
    test_release_identity, test_stream_cancellation,
    test_web_content_security_policy, test_web_navigation_policy). The tenth,
    test_message_actions, DOES `from window import ...` but imports only the
    module-level helper functions (GREETING_TEXT, _is_ephemeral_greeting,
    continue_seed_for_stream, join_continue) -- it never constructs a
    ChatSidebar instance, so it too shows zero entries. In all ten cases the
    zero count is a fact about the script's scope, not a tracer failure.
  - The traced test scripts call os._exit(...) directly in their
    `__main__` guard (bypassing atexit). This wrapper monkeypatches
    os._exit *before* exec'ing the target script so trace data is flushed
    to disk first, then the real os._exit is invoked with the same code.
"""
import sys
import os
import json
import threading

WINDOW_FILE = sys.argv[1]
TARGET_SCRIPT = sys.argv[2]
OUT_JSON = sys.argv[3]

WINDOW_FILE = os.path.abspath(WINDOW_FILE)

entries = {}  # method_name -> {"count": int, "first_line": int}
lock = threading.Lock()

def tracer(frame, event, arg):
    if event == "call":
        code = frame.f_code
        if code.co_filename == WINDOW_FILE:
            varnames = code.co_varnames
            if varnames and varnames[0] == "self" and "self" in frame.f_locals:
                self_obj = frame.f_locals["self"]
                if type(self_obj).__name__ == "ChatSidebar":
                    name = code.co_name
                    with lock:
                        rec = entries.setdefault(name, {"count": 0, "first_line": code.co_firstlineno})
                        rec["count"] += 1
    return tracer

def dump():
    with lock:
        with open(OUT_JSON, "w") as f:
            json.dump(entries, f)

_real_os_exit = os._exit
def _patched_exit(code=0):
    dump()
    _real_os_exit(code)
os._exit = _patched_exit

_real_sys_exit_hook_installed = True

sys.settrace(tracer)
threading.settrace(tracer)

sys.argv = [TARGET_SCRIPT]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(TARGET_SCRIPT))))

global_ns = {"__name__": "__main__", "__file__": os.path.abspath(TARGET_SCRIPT)}

exit_code = 0
try:
    with open(TARGET_SCRIPT) as f:
        src = f.read()
    code_obj = compile(src, TARGET_SCRIPT, "exec")
    exec(code_obj, global_ns)
except SystemExit as e:
    exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
finally:
    sys.settrace(None)
    dump()

sys.exit(exit_code)
