#!/usr/bin/env python3
"""
Stage 1 source inventory generator for ChickenButt window.py / ChatSidebar.

Reproducibility: run as
    python3 extract.py /home/scott/Development/ChickenButt/window.py <outdir>

Pinned to the reviewed HEAD SHA recorded in HEAD_SHORT.txt / the deliverable
report. Uses only the Python standard library `ast` module against the exact
file content on disk -- no semantic guessing, no external claims.

SCOPE OF callbacks.tsv (important -- corrected per Codex review defects 3/6):
  callbacks.tsv is a PATTERN-MATCHED registration inventory, NOT a complete
  callback-boundary model. It captures exactly four syntactic patterns:
  `<x>.connect("signal", cb)`, `GLib.idle_add/timeout_add/timeout_add_seconds`,
  and `threading.Thread(target=...)`. It deliberately does NOT capture:
    * Other GTK async-callback APIs, e.g. `Gtk.FileDialog.save(self, None,
      on_save)` at window.py:1894 -- a real deferred callback boundary not of
      the `.connect` form.
    * Constructor-injected callbacks, e.g. `WebTranscriptView(on_intent=
      self._on_web_intent)` at window.py:800 -- the WebKit->Python intent
      bridge, registered by argument rather than `.connect`.
    * Callbacks forwarded through a local helper parameter named `handler`
      (window.py:1774 in `_make_chat_actions_popover`'s button-builder
      closure, window.py:3275 in the native action-bar builder): these rows
      DO appear in callbacks.tsv but the `callback` column shows the literal
      forwarding lambda / `handler` name, NOT the concrete
      export/delete/edit/regenerate target bound at each call site. Treat
      those callback cells as "unresolved forwarder," not as the final target.
  The `sync_timed_queued_threaded` column for `.connect` rows says
  "GObject/GTK signal handler (delivery deferred to signal emission)" -- it
  does NOT claim the handler runs synchronously at registration time; GTK
  delivers it later when the signal is emitted (often from user input via the
  event loop).

Methodology notes (also restated in checks.txt):
  - "Start line" / "End line" for a method are node.lineno / node.end_lineno
    of the FunctionDef/AsyncFunctionDef node itself (the `def` line through
    its last body line). Decorator lines are NOT included in the line range;
    decorators are listed in their own column instead.
  - "Enclosing ChatSidebar method" is always the nearest enclosing top-level
    method of the ChatSidebar class body (never a closure name).
  - "Enclosing nested closure" is the name of the nearest enclosing nested
    FunctionDef/AsyncFunctionDef/Lambda *inside* that method, or empty if the
    occurrence is directly in the method body (not inside any nested def).
  - AST context labels used in attributes.tsv:
      Load            - self.X read in an expression context not otherwise
                         special-cased below.
      Store           - self.X is the (sole) assignment target of Assign.
      AnnAssign       - self.X is the target of an annotated assignment.
      AugAssign       - self.X is the target of an augmented assignment
                         (+=, -=, etc).
      Del             - `del self.X`.
      Subscript-Store - self.X[...] = ... or self.X[...][...] = ... (write
                         through one or more subscript levels).
      Subscript-Del   - del self.X[...].
      mutation-call   - self.X.<name>(...): X is the immediate receiver of a
                         chained attribute call. No semantic judgement is
                         made about whether <name> actually mutates X; the
                         exact call text is recorded and left for the reader
                         to classify.
      getattr         - getattr(self, "X", ...)
      setattr         - setattr(self, "X", ...)
    A row is only ever assigned ONE context: the most specific one that
    applies to that syntactic occurrence. The same attribute name can and
    will appear in many rows with different contexts; that is intentional
    (reader/writer sets are not mutually exclusive).
  - "MatchesChatSidebarMethodName" (bonus, non-required column): boolean,
    True if the attribute string is also the name of a method in
    methods.tsv. This is a mechanical lookup, not a semantic claim that the
    occurrence *is* a method call; provided so attribute rows that are
    actually `self.<method_name>` references (bound-method / call targets)
    can be told apart from true instance-data attributes by the reader.
"""
import ast
import sys
import csv
import os

def main():
    src_path = sys.argv[1]
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    with open(src_path, "r", encoding="utf-8") as f:
        source = f.read()
    lines = source.splitlines()

    tree = ast.parse(source, filename=src_path)

    # --- locate ChatSidebar class ---
    class_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ChatSidebar":
            class_node = node
            break
    if class_node is None:
        print("ChatSidebar class not found", file=sys.stderr)
        sys.exit(1)

    # --- assign parent pointers to every node in the whole tree ---
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node
    class_node.parent = getattr(class_node, "parent", None)

    def seg(node):
        s = ast.get_source_segment(source, node)
        if s is None:
            return ""
        return s.replace("\n", "\\n")

    # ============ methods.tsv ============
    top_methods = []  # (name, node)
    for stmt in class_node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_methods.append(stmt)

    method_names = {m.name for m in top_methods}
    # duplicate name detection (methods must appear exactly once)
    seen_counts = {}
    for m in top_methods:
        seen_counts[m.name] = seen_counts.get(m.name, 0) + 1

    methods_rows = []
    for m in top_methods:
        decorators = [seg(d) for d in m.decorator_list]
        start = m.lineno
        end = m.end_lineno
        count = end - start + 1
        methods_rows.append({
            "method": m.name,
            "start_line": start,
            "end_line": end,
            "line_count": count,
            "decorators": ";".join(decorators),
            "is_async": isinstance(m, ast.AsyncFunctionDef),
            "duplicate_name_count": seen_counts[m.name],
        })

    with open(os.path.join(outdir, "methods.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["method", "start_line", "end_line", "line_count", "decorators", "is_async", "duplicate_name_count_in_class"])
        for r in methods_rows:
            w.writerow([r["method"], r["start_line"], r["end_line"], r["line_count"], r["decorators"], r["is_async"], r["duplicate_name_count"]])

    # ============ walk each top-level method tracking closures ============
    # context stack of closure names (excludes the top-level method itself)
    attribute_rows = []
    internal_call_rows = []
    callback_rows = []
    external_call_rows = []

    EXTERNAL_RECEIVERS = {"_store", "client", "_web"}

    def enclosing_method_name_for(node):
        # walk up parent chain to the nearest top-level ChatSidebar method
        n = node
        while n is not None:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n in top_methods:
                return n.name
            n = getattr(n, "parent", None)
        return None

    def enclosing_closure_name_for(node, top_method_node):
        # nearest enclosing FunctionDef/AsyncFunctionDef/Lambda that is NOT
        # the top-level method itself
        n = getattr(node, "parent", None)
        while n is not None and n is not top_method_node:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return n.name
            if isinstance(n, ast.Lambda):
                return f"<lambda:L{n.lineno}>"
            n = getattr(n, "parent", None)
        return ""

    def is_self_name(node):
        return isinstance(node, ast.Name) and node.id == "self"

    def classify_attribute(attr_node):
        """attr_node: ast.Attribute with .value being Name('self').
        Returns (context, exact_operation_node, extra_receiver_chain_or_None)
        """
        parent = getattr(attr_node, "parent", None)
        ctx = attr_node.ctx

        if isinstance(ctx, ast.Del):
            # could be del self.x  or del self.x[i]
            if isinstance(parent, ast.Subscript) and parent.value is attr_node:
                cur = parent
                while isinstance(getattr(cur, "parent", None), ast.Subscript) and cur.parent.value is cur:
                    cur = cur.parent
                return ("Subscript-Del", cur)
            return ("Del", attr_node)

        if isinstance(ctx, ast.Store):
            if isinstance(parent, ast.AugAssign) and parent.target is attr_node:
                return ("AugAssign", parent)
            if isinstance(parent, ast.AnnAssign) and parent.target is attr_node:
                return ("AnnAssign", parent)
            if isinstance(parent, ast.Assign):
                return ("Store", parent)
            # tuple/list unpacking target, for-loop target, with-item, etc.
            n = parent
            while isinstance(n, (ast.Tuple, ast.List)):
                n = getattr(n, "parent", None)
            if isinstance(n, ast.Assign):
                return ("Store", n)
            if isinstance(n, ast.For) and (n.target is parent or n.target is n.target):
                return ("Store", n)
            return ("Store", parent if parent is not None else attr_node)

        # Load context
        if isinstance(parent, ast.Subscript) and parent.value is attr_node:
            cur = parent
            while isinstance(getattr(cur, "parent", None), ast.Subscript) and cur.parent.value is cur:
                cur = cur.parent
            if isinstance(cur.ctx, ast.Store):
                return ("Subscript-Store", cur)
            if isinstance(cur.ctx, ast.Del):
                return ("Subscript-Del", cur)
            return ("Load", attr_node)

        if isinstance(parent, ast.Attribute) and parent.value is attr_node:
            gp = getattr(parent, "parent", None)
            if isinstance(gp, ast.Call) and gp.func is parent:
                return ("mutation-call", gp)
            return ("Load", attr_node)

        return ("Load", attr_node)

    # single full-tree walk, tracking top-level-method context via parent chain
    for node in ast.walk(class_node):
        top_method = enclosing_method_name_for(node)
        if top_method is None:
            continue  # not inside any ChatSidebar method (e.g. class-level stmt)
        top_method_node = next(m for m in top_methods if m.name == top_method)
        closure = enclosing_closure_name_for(node, top_method_node)

        # --- self.X attribute occurrences ---
        if isinstance(node, ast.Attribute) and is_self_name(node.value):
            context, op_node = classify_attribute(node)
            attribute_rows.append({
                "attribute": node.attr,
                "line": node.lineno,
                "method": top_method,
                "closure": closure,
                "context": context,
                "operation": seg(op_node),
                "source_text": seg(node),
                "is_method_name": node.attr in method_names,
            })

        # --- getattr(self, "X") / setattr(self, "X", v) ---
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("getattr", "setattr"):
            args = node.args
            if len(args) >= 2 and is_self_name(args[0]) and isinstance(args[1], ast.Constant) and isinstance(args[1].value, str):
                ctxname = "getattr" if node.func.id == "getattr" else "setattr"
                attribute_rows.append({
                    "attribute": args[1].value,
                    "line": node.lineno,
                    "method": top_method,
                    "closure": closure,
                    "context": ctxname,
                    "operation": seg(node),
                    "source_text": seg(node),
                    "is_method_name": args[1].value in method_names,
                })

        # --- internal calls: self.<method>(...) direct (not chained) ---
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and is_self_name(node.func.value):
            callee = node.func.attr
            if callee in method_names:
                internal_call_rows.append({
                    "caller": top_method,
                    "callee": callee,
                    "line": node.lineno,
                    "source_text": seg(node),
                    "closure": closure,
                })

        # --- external calls: self._store / self.client / self._web chains ---
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Attribute) and is_self_name(node.func.value.value):
            receiver_attr = node.func.value.attr
            if receiver_attr in EXTERNAL_RECEIVERS:
                external_call_rows.append({
                    "receiver": f"self.{receiver_attr}",
                    "call_name": node.func.attr,
                    "line": node.lineno,
                    "source_text": seg(node),
                    "method": top_method,
                    "closure": closure,
                })

        # --- ConversationStore(...) local construction + calls on result bound to a name ---
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ConversationStore":
            external_call_rows.append({
                "receiver": "ConversationStore(...)",
                "call_name": "__init__/construct",
                "line": node.lineno,
                "source_text": seg(node),
                "method": top_method,
                "closure": closure,
            })

        # --- callbacks: .connect("signal", callback) ---
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "connect":
            args = node.args
            signal = None
            if args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
                signal = args[0].value
            cb_text = seg(args[1]) if len(args) > 1 else ""
            callback_rows.append({
                "registering_method": top_method,
                "line": node.lineno,
                "mechanism": "connect",
                "signal": signal or "",
                "callback": cb_text,
                "sync_kind": "GObject/GTK signal handler (delivery deferred to signal emission)",
                "closure": closure,
                "source_text": seg(node),
            })

        # --- GLib.idle_add / timeout_add / timeout_add_seconds ---
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "GLib" and node.func.attr in ("idle_add", "timeout_add", "timeout_add_seconds"):
            args = node.args
            if node.func.attr == "idle_add":
                cb_arg = args[0] if args else None
                kind = "queued (GLib.idle_add)"
            else:
                cb_arg = args[1] if len(args) > 1 else None
                kind = f"timed ({node.func.attr})"
            callback_rows.append({
                "registering_method": top_method,
                "line": node.lineno,
                "mechanism": f"GLib.{node.func.attr}",
                "signal": "",
                "callback": seg(cb_arg) if cb_arg is not None else "",
                "sync_kind": kind,
                "closure": closure,
                "source_text": seg(node),
            })

        # --- threading.Thread(target=...) ---
        if isinstance(node, ast.Call) and (
            (isinstance(node.func, ast.Attribute) and node.func.attr == "Thread" and isinstance(node.func.value, ast.Name) and node.func.value.id == "threading")
            or (isinstance(node.func, ast.Name) and node.func.id == "Thread")
        ):
            target = None
            for kw in node.keywords:
                if kw.arg == "target":
                    target = kw.value
            callback_rows.append({
                "registering_method": top_method,
                "line": node.lineno,
                "mechanism": "threading.Thread",
                "signal": "",
                "callback": seg(target) if target is not None else "",
                "sync_kind": "threaded",
                "closure": closure,
                "source_text": seg(node),
            })

    with open(os.path.join(outdir, "attributes.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["attribute", "line", "enclosing_method", "enclosing_closure", "ast_context", "exact_operation", "exact_source_text", "matches_chatsidebar_method_name"])
        for r in sorted(attribute_rows, key=lambda r: (r["line"], r["attribute"])):
            w.writerow([r["attribute"], r["line"], r["method"], r["closure"], r["context"], r["operation"], r["source_text"], r["is_method_name"]])

    with open(os.path.join(outdir, "internal-calls.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["caller_method", "callee_method", "line", "source_text", "enclosing_closure"])
        for r in sorted(internal_call_rows, key=lambda r: r["line"]):
            w.writerow([r["caller"], r["callee"], r["line"], r["source_text"], r["closure"]])

    with open(os.path.join(outdir, "callbacks.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["registering_method", "registration_line", "mechanism", "signal", "callback", "sync_timed_queued_threaded", "enclosing_closure", "source_text"])
        for r in sorted(callback_rows, key=lambda r: r["line"]):
            w.writerow([r["registering_method"], r["line"], r["mechanism"], r["signal"], r["callback"], r["sync_kind"], r["closure"], r["source_text"]])

    with open(os.path.join(outdir, "external-calls.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["receiver", "call_or_construct", "line", "source_text", "enclosing_method", "enclosing_closure"])
        for r in sorted(external_call_rows, key=lambda r: r["line"]):
            w.writerow([r["receiver"], r["call_name"], r["line"], r["source_text"], r["method"], r["closure"]])

    # --- also dump raw facts needed for checks.txt to stdout as a small json-ish summary ---
    print(f"ChatSidebar class: lines {class_node.lineno}-{class_node.end_lineno}")
    print(f"top-level methods: {len(top_methods)}")
    print(f"duplicate method names: {[n for n,c in seen_counts.items() if c>1]}")
    print(f"attribute rows: {len(attribute_rows)}")
    print(f"internal call rows: {len(internal_call_rows)}")
    print(f"callback rows: {len(callback_rows)}")
    print(f"external call rows: {len(external_call_rows)}")

if __name__ == "__main__":
    main()
