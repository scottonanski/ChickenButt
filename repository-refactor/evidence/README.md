# Refactor evidence baselines

This directory preserves independently reviewed evidence used to evaluate the
refactor research and planning drafts. Evidence acceptance establishes a
factual baseline only; it does not approve ownership decisions, phase ordering,
implementation work, or changes to application code.

## `window.py` / `ChatSidebar` audit

- Evidence bundle: `window-audit-d12bf2e/`
- Reviewed repository HEAD:
  `d12bf2e71eb61d3440bd8f5ed1f937ff33bc9d04`
- Reviewed `window.py` SHA-256:
  `c52eb30856cbfeb65261bbe97c6b46ef5afa2ba41a00fd48c1b95d9ae7b1ced1`
- Independent-review status: accepted as a factual baseline on 2026-07-23
- Bundle contents: eight generators, mechanically generated inventories and
  test/runtime evidence, the separately authored `discrepancies.md`, and a
  68-entry SHA-256 manifest

The accepted bundle is pinned to the reviewed source. If `HEAD` or
`window.py` changes, create a new versioned evidence bundle instead of editing
this one in place.

### Verify the preserved bundle

From the repository root:

```bash
(
  cd repository-refactor/evidence/window-audit-d12bf2e
  sha256sum -c MANIFEST-sha256.txt
)
```

### Reproduce against the reviewed source

The orchestrator enforces the pinned HEAD and `window.py` hash. Because the
documentation commits that preserve this bundle advance the main checkout
beyond the reviewed source commit, create a detached temporary worktree at the
reviewed HEAD. Run the repository-local orchestrator against that worktree and
write results to a fresh target so the preserved evidence remains unchanged:

```bash
audit_dir="$PWD/repository-refactor/evidence/window-audit-d12bf2e"
review_parent="$(mktemp -d /tmp/chickenbutt-window-reviewed-XXXXXX)"
review_tree="$review_parent/source"
rerun_dir="$(mktemp -d /tmp/chickenbutt-window-audit-rerun-XXXXXX)"
git worktree add --detach "$review_tree" \
  d12bf2e71eb61d3440bd8f5ed1f937ff33bc9d04
"$audit_dir/gen/orchestrate.sh" \
  "$review_tree" \
  "$review_tree/window.py" \
  "$rerun_dir/out"
git worktree remove "$review_tree"
rmdir "$review_parent"
```

Expected baseline results are 15/15 normal test scripts passing, 217 runtime
`(script, method)` rows, 53/99 `ChatSidebar` methods observed, and five scripts
with at least one `ChatSidebar` entry. Runtime entry-count integers for the five
composer-layout methods are timing-sensitive; conclusions use the stable
`(script, method)` key set instead.

### Interpretation limits

- Method entry proves execution, not branch or assertion coverage.
- `sys.settrace` and `threading.settrace` do not trace child OS subprocesses.
- The callback inventory is explicitly pattern-matched rather than exhaustive
  semantic callback resolution.
- Method-name searches alone are not accepted as coverage evidence.
- `discrepancies.md` is an authored comparison against the drafts, not a
  mechanically generated artifact.
