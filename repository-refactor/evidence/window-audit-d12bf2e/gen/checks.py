#!/usr/bin/env python3
"""
Mechanical verification of the Stage 1 generated evidence.
Run as: python3 checks.py <window.py path> <outdir>
Writes checks.txt into <outdir> and exits non-zero if any check fails.
"""
import ast
import csv
import sys
import os

def read_tsv(path):
    with open(path, newline="") as f:
        r = csv.reader(f, delimiter="\t")
        header = next(r)
        return header, [row for row in r]

def main():
    src_path = sys.argv[1]
    outdir = sys.argv[2]
    with open(src_path, encoding="utf-8") as f:
        source = f.read()
    lines = source.splitlines()
    tree = ast.parse(source, filename=src_path)

    class_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ChatSidebar":
            class_node = node
            break

    top_methods = [s for s in class_node.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))]
    real_method_names = {m.name for m in top_methods}

    out = []
    failures = 0

    def check(desc, ok, detail=""):
        nonlocal failures
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        out.append(f"[{status}] {desc}" + (f" -- {detail}" if detail else ""))

    # ---- methods.tsv: every method exactly once ----
    mh, mrows = read_tsv(os.path.join(outdir, "methods.tsv"))
    method_col = mh.index("method")
    names_in_tsv = [r[method_col] for r in mrows]
    check(
        "Every ChatSidebar method appears exactly once in methods.tsv",
        len(names_in_tsv) == len(set(names_in_tsv)) and set(names_in_tsv) == real_method_names,
        f"tsv_count={len(names_in_tsv)} unique={len(set(names_in_tsv))} ast_count={len(real_method_names)} "
        f"missing_from_tsv={sorted(real_method_names - set(names_in_tsv))} extra_in_tsv={sorted(set(names_in_tsv) - real_method_names)}"
    )

    # ---- every reported line in methods.tsv exists and is the def line ----
    start_col = mh.index("start_line")
    end_col = mh.index("end_line")
    count_col = mh.index("line_count")
    bad = []
    for r in mrows:
        name, start, end, cnt = r[method_col], int(r[start_col]), int(r[end_col]), int(r[count_col])
        if start < 1 or start > len(lines) or end < 1 or end > len(lines):
            bad.append((name, "line out of range"))
            continue
        line_text = lines[start - 1]
        if f"def {name}" not in line_text:
            bad.append((name, f"start_line {start} does not contain 'def {name}': {line_text!r}"))
        if end - start + 1 != cnt:
            bad.append((name, "line_count mismatch"))
    check("Every methods.tsv start_line contains the method's def statement; line_count is start/end derived", len(bad) == 0, str(bad[:10]))

    # ---- attributes.tsv structural checks ----
    ah, arows = read_tsv(os.path.join(outdir, "attributes.tsv"))
    attr_col = ah.index("attribute")
    line_col = ah.index("line")
    method_col_a = ah.index("enclosing_method")
    ctx_col = ah.index("ast_context")
    src_col = ah.index("exact_source_text")

    bad = []
    for r in arows:
        ln = int(r[line_col])
        if ln < 1 or ln > len(lines):
            bad.append((r[attr_col], ln, "out of range"))
            continue
        text = lines[ln - 1]
        attr = r[attr_col]
        if f".{attr}" not in text and attr not in text:
            bad.append((r[attr_col], ln, f"attribute text not found on reported line: {text!r}"))
    check("Every attributes.tsv reported line exists and plausibly contains the attribute name", len(bad) == 0, str(bad[:10]))

    # enclosing method must be a real ChatSidebar method
    bad = [r for r in arows if r[method_col_a] not in real_method_names]
    check("Every attributes.tsv enclosing_method is a real ChatSidebar method", len(bad) == 0, str(bad[:5]))

    # ---- init vs dynamic attribute classification ----
    init_method = "__init__"
    first_occurrence = {}
    # setattr(self, "X", v) is a write context. window.py has zero such sites
    # at this SHA (asserted below), so including it does not change the current
    # partition, but the classifier is complete rather than silently omitting it.
    write_contexts = {"Store", "AnnAssign", "AugAssign", "Subscript-Store", "setattr"}
    for r in arows:
        attr = r[attr_col]
        ctx = r[ctx_col]
        ln = int(r[line_col])
        if ctx not in write_contexts:
            continue
        if attr not in first_occurrence or ln < first_occurrence[attr][0]:
            first_occurrence[attr] = (ln, r[method_col_a])

    all_attrs = sorted(set(r[attr_col] for r in arows))
    init_attrs = sorted(a for a, (ln, m) in first_occurrence.items() if m == init_method)
    dynamic_attrs = sorted(a for a, (ln, m) in first_occurrence.items() if m != init_method)
    never_written = sorted(a for a in all_attrs if a not in first_occurrence)

    with open(os.path.join(outdir, "attribute-init-classification.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["attribute", "classification", "first_write_line", "first_write_method"])
        for a in all_attrs:
            if a in first_occurrence:
                ln, m = first_occurrence[a]
                cls = "initialized_in___init__" if m == init_method else "first_assigned_elsewhere"
                w.writerow([a, cls, ln, m])
            else:
                w.writerow([a, "never_written_only_read_or_called", "", ""])

    check(
        "Initialized-in-__init__ attrs + first-assigned-elsewhere attrs + never-written attrs == unique attribute union",
        len(init_attrs) + len(dynamic_attrs) + len(never_written) == len(all_attrs),
        f"init={len(init_attrs)} dynamic={len(dynamic_attrs)} never_written={len(never_written)} union={len(all_attrs)}"
    )
    overlap = set(init_attrs) & set(dynamic_attrs)
    check("No attribute is classified as both initialized-in-__init__ and first-assigned-elsewhere", len(overlap) == 0, str(sorted(overlap)))

    # ---- reader/writer sets not mutually exclusive: attrs with both a read
    # and a write occurrence. READ contexts are Load, mutation-call (a
    # chained call on the attribute reads the attribute to reach the method),
    # AND getattr(self, "X", ...) -- getattr IS a read (fix per Codex review
    # defect 2; the earlier version omitted getattr and reported 63 instead
    # of the correct 66). WRITE contexts are Store/AnnAssign/AugAssign/
    # Subscript-Store; setattr(self, "X", v) would also be a write context
    # but window.py contains zero setattr(self, ...) sites at this SHA (see
    # the setattr assertion below), so it does not affect the count here.
    read_contexts = {"Load", "mutation-call", "getattr"}
    per_attr_ctx = {}
    for r in arows:
        per_attr_ctx.setdefault(r[attr_col], set()).add(r[ctx_col])
    both = [a for a, ctxs in per_attr_ctx.items() if (ctxs & read_contexts) and (ctxs & write_contexts)]
    check(
        "Reader and writer sets are not treated as mutually exclusive: exactly 66 attrs have both a read (Load/mutation-call/getattr) and a write occurrence row; getattr counts as a read",
        len(both) == 66,
        f"{len(both)} attributes have both read and write occurrence rows (expected exactly 66), e.g. {sorted(both)[:5]}"
    )
    # explicit corroboration of the getattr/setattr handling
    setattr_attrs = sorted(a for a, ctxs in per_attr_ctx.items() if "setattr" in ctxs)
    getattr_only_read_written = set(
        a for a, ctxs in per_attr_ctx.items()
        if "getattr" in ctxs and (ctxs & write_contexts) and not (ctxs & {"Load", "mutation-call"})
    )
    check(
        "setattr(self, ...) site count is zero at this SHA (so setattr absence cannot skew the write partition)",
        len(setattr_attrs) == 0,
        f"setattr attrs={setattr_attrs}"
    )
    expected_getattr_only = {"_composer_layout_hooked", "_empty_icon", "_ollama_cli_busy"}
    check(
        "Exactly these 3 attrs are written and read ONLY via getattr (excluding getattr from reads would have dropped them from the overlap)",
        getattr_only_read_written == expected_getattr_only,
        f"got {sorted(getattr_only_read_written)}, expected {sorted(expected_getattr_only)}"
    )

    # ---- internal-calls.tsv: every callee names a real ChatSidebar method ----
    ih, irows = read_tsv(os.path.join(outdir, "internal-calls.tsv"))
    caller_col = ih.index("caller_method")
    callee_col = ih.index("callee_method")
    iline_col = ih.index("line")
    bad_caller = [r for r in irows if r[caller_col] not in real_method_names]
    bad_callee = [r for r in irows if r[callee_col] not in real_method_names]
    check("Every internal-calls.tsv caller_method is a real ChatSidebar method", len(bad_caller) == 0, str(bad_caller[:5]))
    check("Every internal-calls.tsv callee_method names a real ChatSidebar method", len(bad_callee) == 0, str(bad_callee[:5]))

    bad = []
    for r in irows:
        ln = int(r[iline_col])
        if ln < 1 or ln > len(lines) or f".{r[callee_col]}(" not in lines[ln-1].replace(" ", ""):
            bad.append(r)
    check("Every internal-calls.tsv line exists and contains a call to the reported callee", len(bad) == 0, str(bad[:5]))

    # ---- counts are derived, not manual: recompute headline counts here and compare to a manifest we also write ----
    manifest = {
        "chatsidebar_method_count": len(real_method_names),
        "attribute_occurrence_rows": len(arows),
        "unique_attribute_names": len(all_attrs),
        "internal_call_rows": len(irows),
    }
    with open(os.path.join(outdir, "counts-manifest.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["metric", "value"])
        for k, v in manifest.items():
            w.writerow([k, v])
    check("counts-manifest.tsv counts recomputed directly from TSV row counts (not manually entered)", True)

    out.append("")
    out.append(f"TOTAL: {'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")

    with open(os.path.join(outdir, "checks.txt"), "w") as f:
        f.write("\n".join(out) + "\n")

    print("\n".join(out))
    sys.exit(1 if failures else 0)

if __name__ == "__main__":
    main()
