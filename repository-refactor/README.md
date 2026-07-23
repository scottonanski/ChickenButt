# Repository Refactor — Index

This directory holds the active documentation for ChickenButt's
repository-refactor effort, which began after repository recovery closed
2026-07-23 (see `../recovery-reports/`, which is historical evidence only
and is not part of this effort).

- **`REFACTOR_PLAN.md`** — the single active authority. Proposed phases,
  Scott's decisions, and the ledger of completed work live here. If it's
  not in this file, it isn't approved.
- **`research/`** — evidence reports backing the plan. Reports provide
  evidence; they do not authorize implementation by themselves.

| Report | Subject |
|---|---|
| `research/00-window-audit.md` | `window.py` / `ChatSidebar` responsibility map, dependency tracing, test-coverage assessment, and proposed extraction phases |

Do not create competing status, handoff, or roadmap files in this
directory — extend `REFACTOR_PLAN.md` instead.
