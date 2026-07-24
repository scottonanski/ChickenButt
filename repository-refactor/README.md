# Repository Refactor — Index

This directory holds the active documentation for ChickenButt's
repository-refactor effort, which began after repository recovery closed
2026-07-23 (see `../recovery-reports/`, which is historical evidence only
and is not part of this effort).

- **`REFACTOR_PLAN.md`** — the single active authority. Proposed phases,
  Scott's decisions, and verified completion reports live here. After a
  phase succeeds, its proposal is replaced in place by its factual completion
  report; progress is not appended as a separate ledger. If it is not in this
  file, it is not approved or complete.
- **`research/`** — evidence reports backing the plan. Reports provide
  evidence; they do not authorize implementation by themselves.

| Report | Subject |
|---|---|
| `research/00-window-audit.md` | `window.py` / `ChatSidebar` responsibility map, dependency tracing, test-coverage assessment, and proposed extraction phases |

Do not create competing status, handoff, progress-log, or roadmap files in
this directory — update the applicable phase and any affected current-state
claims in `REFACTOR_PLAN.md` instead.
