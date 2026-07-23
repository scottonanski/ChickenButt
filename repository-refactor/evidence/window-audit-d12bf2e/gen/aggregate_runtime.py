#!/usr/bin/env python3
"""
Aggregate per-script trace JSON files (produced by run_traced.py) into
runtime-method-entries.tsv. Previously this was an inline heredoc; it is now
a committed, hashed generator so the aggregation step is reproducible
(Codex review methodological rec 2).

Usage: python3 aggregate_runtime.py <outdir>
  reads   <outdir>/trace-json/*.json
  writes  <outdir>/runtime-method-entries.tsv

NOTE ON DETERMINISM: entry_count values are timing-sensitive for the five
composer-layout methods (_apply_composer_height, _composer_line_height_px,
_composer_max_visible_lines, _composer_content_height_px,
_sync_composer_action_valign) because those fire from GLib layout callbacks
whose iteration count depends on event-loop timing. Across independent runs
the SET of (script, method) keys and the observed-method union are stable;
only some entry_count integers vary. Downstream coverage conclusions therefore
key off the observed method SET, never the exact counts. The `first_observed_source_line_def`
column is the method's def line (co_firstlineno), which is fully stable.
"""
import json
import os
import sys
import csv

def main():
    outdir = sys.argv[1]
    tdir = os.path.join(outdir, "trace-json")
    scripts = sorted(f[:-5] for f in os.listdir(tdir) if f.endswith(".json"))

    rows = []
    for s in scripts:
        with open(os.path.join(tdir, f"{s}.json")) as f:
            data = json.load(f)
        for method, rec in data.items():
            rows.append((s, method, rec["count"], rec["first_line"]))

    # deterministic ordering: script asc, then entry_count desc, then method asc
    rows.sort(key=lambda r: (r[0], -r[2], r[1]))
    with open(os.path.join(outdir, "runtime-method-entries.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["test_script", "chatsidebar_method", "entry_count", "first_observed_source_line_def"])
        for r in rows:
            w.writerow(r)

    scripts_with_entries = sorted(s for s in scripts
                                  if json.load(open(os.path.join(tdir, f"{s}.json"))))
    print(f"total rows: {len(rows)}")
    print(f"scripts with >=1 ChatSidebar entry: {len(scripts_with_entries)} -> {scripts_with_entries}")

if __name__ == "__main__":
    main()
