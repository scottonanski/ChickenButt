#!/usr/bin/env python3
"""
Build test-evidence.md by combining:
  - methods.tsv               (full ChatSidebar method inventory)
  - runtime-method-entries.tsv (per-script traced method entries)
  - direct-test-calls.tsv      (receiver-aware direct invocations)
  - internal-calls.tsv         (static ChatSidebar-internal call graph)

Let `direct` = methods with a syntactic direct call in the script's test
source (direct-test-calls.tsv, receiver_class == ChatSidebar), and
`runtime` = methods with entry_count > 0 in runtime-method-entries.tsv for
that script. EXECUTION evidence is `runtime` alone; a syntactic direct call
is not itself execution evidence. Category assignment per (script, method):

  1. Directly invoked by test code AND executed = `direct ∩ runtime`.
  2. Runtime-observed indirectly              = `runtime − direct`.
  3. Statically reachable but not runtime-observed = methods reachable via a
     BFS over internal-calls.tsv starting from the `runtime`-observed set,
     EXCLUDING the runtime-observed methods themselves.
  4. No execution evidence in this run        = all remaining methods (not in
     categories 1-3).

Categories 1-4 are mutually exclusive and partition all 99 methods.
Additionally, `direct − runtime` (syntactically direct-called but never
observed executing) is reported SEPARATELY on its own per-script line as
syntactic-only evidence -- it is NOT folded into any execution category. In
this run `direct − runtime` is empty for every script (every syntactic
direct ChatSidebar call was also traced).

"Method entered, branch coverage unknown" is not a disjoint bucket: it is a
caveat that applies to every method in categories 1 and 2 (entry was
observed, but which branches/lines inside the method executed is NOT
determined by method-entry tracing).

A method absent from a script's runtime trace is NEVER described as
"completely untested" -- only as having no execution evidence in *this run*
of *this script*; it may be covered by a different one of the 15 scripts,
by branches not exercised this run, or the absence may simply reflect that
the script targets a different subsystem entirely (see per-script notes).
"""
import csv
import os
import sys
from collections import defaultdict

def read_tsv(path):
    with open(path, newline="") as f:
        r = csv.reader(f, delimiter="\t")
        header = next(r)
        return header, [row for row in r]

def main():
    outdir = sys.argv[1]

    mh, mrows = read_tsv(os.path.join(outdir, "methods.tsv"))
    all_methods = [r[mh.index("method")] for r in mrows]

    ih, irows = read_tsv(os.path.join(outdir, "internal-calls.tsv"))
    caller_col, callee_col = ih.index("caller_method"), ih.index("callee_method")
    call_graph = defaultdict(set)
    for r in irows:
        call_graph[r[caller_col]].add(r[callee_col])

    rh, rrows = read_tsv(os.path.join(outdir, "runtime-method-entries.tsv"))
    rscript_col, rmethod_col, rcount_col = rh.index("test_script"), rh.index("chatsidebar_method"), rh.index("entry_count")
    runtime_by_script = defaultdict(set)
    for r in rrows:
        if int(r[rcount_col]) > 0:
            runtime_by_script[r[rscript_col]].add(r[rmethod_col])

    dh, drows = read_tsv(os.path.join(outdir, "direct-test-calls.tsv"))
    dscript_col, dclass_col, dmethod_col = dh.index("test_script"), dh.index("receiver_class"), dh.index("method")
    direct_by_script = defaultdict(set)
    for r in drows:
        if r[dclass_col] == "ChatSidebar" and r[dmethod_col] in all_methods:
            script = r[dscript_col][:-3] if r[dscript_col].endswith(".py") else r[dscript_col]
            direct_by_script[script].add(r[dmethod_col])

    scripts = sorted(set(list(runtime_by_script) + list(direct_by_script)) | {
        f[:-5] for f in os.listdir(os.path.join(outdir, "trace-json")) if f.endswith(".json")
    })

    lines = []
    lines.append("# test-evidence.md")
    lines.append("")
    lines.append("Generated from methods.tsv, internal-calls.tsv, runtime-method-entries.tsv, "
                  "direct-test-calls.tsv. See gen/test_evidence.py docstring for exact category rules.")
    lines.append("")
    lines.append("**Caveat (applies to every 'Directly invoked' and 'Runtime-observed indirectly' row below):** "
                  "method entry was observed via sys.settrace/threading.settrace; this proves the method's body "
                  "started executing at least once in this run of this script. It does NOT prove which internal "
                  "branches, early returns, or exception paths within that method executed. No claim of full "
                  "branch coverage is made anywhere in this document.")
    lines.append("")

    summary_counts = {}

    for script in scripts:
        direct = direct_by_script.get(script, set())
        runtime = runtime_by_script.get(script, set())
        # EXECUTION evidence per script == runtime traces only. A syntactic
        # direct call in test source is NOT itself execution evidence (Codex
        # review defect 4); it only counts as "directly invoked" when it was
        # ALSO observed at runtime. Syntactic-direct-but-not-traced methods are
        # reported in their own line as syntactic evidence, never folded into
        # execution categories.
        observed = set(runtime)
        # BFS over static call graph from the runtime-observed set
        seen = set(observed)
        frontier = list(observed)
        while frontier:
            cur = frontier.pop()
            for callee in call_graph.get(cur, ()):
                if callee not in seen:
                    seen.add(callee)
                    frontier.append(callee)
        static_only = seen - observed

        cat1 = sorted(direct & runtime)             # directly invoked AND executed
        cat2 = sorted(runtime - direct)             # runtime-observed indirectly
        cat3 = sorted(static_only)                  # statically reachable, not executed
        cat4 = sorted(set(all_methods) - seen)      # no execution evidence this run
        direct_not_observed = sorted(direct - runtime)  # syntactic only, not executed

        summary_counts[script] = (len(cat1), len(cat2), len(cat3), len(cat4))

        lines.append(f"## {script}")
        lines.append("")
        lines.append(f"- Directly invoked by test code AND executed at runtime: {len(cat1)}")
        lines.append(f"- Runtime-observed indirectly: {len(cat2)}")
        lines.append(f"- Statically reachable but not runtime-observed: {len(cat3)}")
        lines.append(f"- No execution evidence in this run: {len(cat4)}")
        lines.append(f"- Syntactically directly-called in test source but NOT observed executing "
                      f"(syntactic evidence only, not execution): {len(direct_not_observed)}")
        lines.append(f"- (Total ChatSidebar methods: {len(all_methods)})")
        lines.append("")
        if cat1:
            lines.append(f"**Directly invoked and executed:** {', '.join(cat1)}")
            lines.append("")
        if direct_not_observed:
            lines.append(f"**Syntactically direct-called but not observed executing:** "
                          f"{', '.join(direct_not_observed)}")
            lines.append("")
        if cat2:
            lines.append(f"**Runtime-observed indirectly (alphabetical, first 30; full set in "
                          f"runtime-method-entries.tsv -- entry counts are timing-sensitive so no "
                          f"count-ranking is asserted):** "
                          f"{', '.join(cat2[:30])}" + (" ..." if len(cat2) > 30 else ""))
            lines.append("")
        if cat3:
            lines.append(f"**Statically reachable, not observed this run:** {', '.join(cat3[:30])}"
                          + (" ..." if len(cat3) > 30 else ""))
            lines.append("")
        lines.append("")

    lines.append("## Summary table")
    lines.append("")
    lines.append("| script | directly invoked & executed | runtime-observed indirectly | statically reachable, not observed | no execution evidence |")
    lines.append("|---|---|---|---|---|")
    for script in scripts:
        c1, c2, c3, c4 = summary_counts[script]
        lines.append(f"| {script} | {c1} | {c2} | {c3} | {c4} |")
    lines.append("")

    lines.append("## Scripts with zero ChatSidebar involvement")
    lines.append("")
    lines.append("The following scripts produce zero ChatSidebar method entries and zero syntactic "
                  "direct ChatSidebar calls (they test other modules/behaviors: dependency checking, "
                  "installed-layout/meson, release identity, WebKit CSP/navigation policy via a bare "
                  "WebView, ConversationStore directly, or the ollama_health module). Nine never import "
                  "`window.ChatSidebar`; the tenth, `test_message_actions`, imports only module-level "
                  "helper functions from `window` and never constructs the class. Zero ChatSidebar "
                  "entries here is a fact about the script's scope, not a tracer gap:")
    lines.append("")
    zero_scripts = [s for s in scripts if s not in runtime_by_script and s not in direct_by_script]
    for s in zero_scripts:
        lines.append(f"- {s}")
    lines.append("")

    lines.append("## Union across all 15 scripts")
    lines.append("")
    # RUNTIME execution evidence must come from the runtime traces alone --
    # direct-test-calls.tsv is a SYNTACTIC search of test source and does not
    # by itself prove execution (Codex review methodological note). In this
    # run every syntactically-direct ChatSidebar call was ALSO traced, so the
    # two unions coincide; we compute and report both to make that explicit
    # rather than silently folding the syntactic set into "execution".
    runtime_union = set()
    for s in scripts:
        runtime_union |= runtime_by_script.get(s, set())
    direct_union = set()
    for s in scripts:
        direct_union |= direct_by_script.get(s, set())
    union_observed = runtime_union  # execution evidence == runtime rows only
    direct_not_traced = sorted(direct_union - runtime_union)
    never_observed_anywhere = sorted(set(all_methods) - union_observed)
    lines.append(f"- Methods with RUNTIME execution evidence (entered per runtime-method-entries.tsv) in "
                  f"AT LEAST ONE of the 15 scripts: **{len(runtime_union)} / {len(all_methods)}**")
    lines.append(f"- Methods syntactically directly-invoked in test source (direct-test-calls.tsv, "
                  f"receiver_class==ChatSidebar) across all scripts: {len(direct_union)} "
                  f"(all of which were also traced this run; syntactically-direct-but-not-traced: "
                  f"{direct_not_traced if direct_not_traced else 'none'})")
    lines.append(f"- Methods with NO runtime execution evidence in ANY of the 15 scripts this run: "
                  f"**{len(never_observed_anywhere)} / {len(all_methods)}**")
    lines.append("")
    lines.append("Methods never observed executing in this run (may still be statically reachable, "
                  "may be UI-callback-only paths not exercised by the current scripted interactions, "
                  "or may be genuinely dead/unreachable from tested entry points -- this run does not "
                  "distinguish those cases):")
    lines.append("")
    for m in never_observed_anywhere:
        lines.append(f"- {m}")
    lines.append("")

    with open(os.path.join(outdir, "test-evidence.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"scripts covered: {len(scripts)}")
    print(f"union observed: {len(union_observed)}/{len(all_methods)}")
    print(f"never observed anywhere: {len(never_observed_anywhere)}")

if __name__ == "__main__":
    main()
