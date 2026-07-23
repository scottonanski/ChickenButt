#!/usr/bin/env python3
"""
Receiver-aware direct invocation scan of scripts/test_*.py files.

For each test script:
  1. Find all `var = ClassName(...)` bindings, where ClassName is either a
     class defined in that same test file (ast.ClassDef) or one of the
     production classes we care about (ChatSidebar, ConversationStore,
     OllamaClient, WebTranscriptView, MessageBody, MarkdownView, CodeBlock).
     Re-binding a name updates its tracked class (last assignment wins,
     matching normal Python name-binding semantics for these short,
     linear test scripts).
  2. Find every `var.method(...)` call where `var` is currently tracked,
     and record (test_script, receiver_var, receiver_class, method, line,
     source_text).

This is purely syntactic/mechanical: no attempt is made to guess a
receiver's class when it wasn't produced by a traceable `= ClassName(...)`
assignment in the same file (e.g. items pulled out of a list, loop
variables, function-return values from helpers) -- those calls are
reported with receiver_class = "<unresolved>" rather than silently
attributed to ChatSidebar.
"""
import ast
import csv
import os
import sys

KNOWN_IMPORTED_CLASSES = {
    "ChatSidebar", "ConversationStore", "OllamaClient", "WebTranscriptView",
    "MessageBody", "MarkdownView", "CodeBlock",
}

def scan_file(path):
    with open(path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=path)
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    local_classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    trackable_classes = KNOWN_IMPORTED_CLASSES | local_classes

    def seg(n):
        s = ast.get_source_segment(source, n)
        return s.replace("\n", "\\n") if s else ""

    def receiver_key(expr):
        """Return a stable string key for a Name or constant-keyed Subscript
        chain (e.g. holder["win"] -> 'holder["win"]'), else None if the
        receiver expression can't be resolved to a trackable binding."""
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Subscript):
            base = receiver_key(expr.value)
            if base is None:
                return None
            idx = expr.slice
            if isinstance(idx, ast.Constant):
                return f'{base}[{idx.value!r}]'
            return None
        return None

    var_class = {}
    rows = []

    # single pass in source order: process Assign bindings and Call
    # invocations as we encounter them (ast.walk is not perfectly source
    # ordered across separate statements at different nesting depths, so
    # sort all relevant nodes by lineno/col_offset first).
    relevant = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.value, ast.Call):
            key = receiver_key(node.targets[0])
            if key is not None:
                callee = node.value.func
                cname = None
                if isinstance(callee, ast.Name) and callee.id in trackable_classes:
                    cname = callee.id
                if cname:
                    relevant.append((node.lineno, node.col_offset, "bind", key, cname, node))
        # `var: ClassName = <anything>` -- an explicit type annotation is a
        # stronger, purely syntactic receiver-class signal than tracing the
        # RHS expression, and covers `win: ChatSidebar = holder["win"]`
        # patterns used to pull a widget back out of a mutable closure cell.
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and isinstance(node.annotation, ast.Name):
            if node.annotation.id in trackable_classes:
                relevant.append((node.lineno, node.col_offset, "bind", node.target.id, node.annotation.id, node))
        # `var = <other tracked var or subscript>` -- propagate the class of
        # an already-tracked receiver through a plain re-binding, e.g.
        # `win = holder["w"]` after `holder["w"] = ChatSidebar(...)`.
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and not isinstance(node.value, ast.Call):
            tgt_key = receiver_key(node.targets[0])
            src_key = receiver_key(node.value)
            if tgt_key is not None and src_key is not None:
                relevant.append((node.lineno, node.col_offset, "propagate", tgt_key, src_key, node))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            key = receiver_key(node.func.value)
            if key is not None:
                relevant.append((node.lineno, node.col_offset, "call", key, node.func.attr, node))

    relevant.sort(key=lambda t: (t[0], t[1]))

    for lineno, col, kind, a, b, node in relevant:
        if kind == "bind":
            var_class[a] = b
        elif kind == "propagate":
            if b in var_class:
                var_class[a] = var_class[b]
        else:
            varname, method = a, b
            rcls = var_class.get(varname, "<unresolved>")
            rows.append({
                "script": os.path.basename(path),
                "receiver_var": varname,
                "receiver_class": rcls,
                "method": method,
                "line": lineno,
                "source_text": seg(node),
            })
    return rows

def main():
    scripts_dir = sys.argv[1]
    outdir = sys.argv[2]
    all_rows = []
    for fname in sorted(os.listdir(scripts_dir)):
        if fname.startswith("test_") and fname.endswith(".py"):
            all_rows.extend(scan_file(os.path.join(scripts_dir, fname)))

    with open(os.path.join(outdir, "direct-test-calls.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["test_script", "receiver_var", "receiver_class", "method", "line", "source_text"])
        for r in all_rows:
            w.writerow([r["script"], r["receiver_var"], r["receiver_class"], r["method"], r["line"], r["source_text"]])

    chatsidebar_rows = [r for r in all_rows if r["receiver_class"] == "ChatSidebar"]
    print(f"total direct-call rows: {len(all_rows)}")
    print(f"rows attributed to ChatSidebar receiver: {len(chatsidebar_rows)}")
    by_script = {}
    for r in chatsidebar_rows:
        by_script.setdefault(r["script"], set()).add(r["method"])
    for s, methods in sorted(by_script.items()):
        print(f"  {s}: {sorted(methods)}")

if __name__ == "__main__":
    main()
