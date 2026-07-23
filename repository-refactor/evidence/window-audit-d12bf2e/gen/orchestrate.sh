#!/usr/bin/env bash
# Full reproducible pipeline for the window.py / ChatSidebar audit evidence.
# Committed and hashed per Codex review methodological rec 2. This script
# regenerates every MECHANICALLY GENERATED artifact under <outdir>. It does
# NOT (re)generate out/discrepancies.md: that is a separately authored review
# document (Stage 4), not machine-derived evidence -- it is pinned in
# MANIFEST-sha256.txt but produced by hand, and this orchestrator deliberately
# leaves any existing copy untouched.
#
# Usage:
#   gen/orchestrate.sh <repo_root> <window.py path> <outdir>
#
# FAIL-CLOSED (Codex review 2, defect 2): runs under `set -euo pipefail`;
# every generator failure, trace timeout, or trace nonzero exit aborts the run.
# The pinned HEAD and window.py SHA-256 are ENFORCED, not merely recorded.
# <outdir> must not already contain generated artifacts unless --clean is given.
#
# Determinism knobs:
#   PYTHONDONTWRITEBYTECODE=1  -- do not litter scripts/__pycache__
#   PYTHONHASHSEED=0           -- stabilize set/dict iteration (all our TSV
#                                 writers also sort explicitly; belt-and-braces)
set -euo pipefail

REPO="${1:?repo root}"
WINDOW="${2:?window.py path}"
OUT="${3:?outdir}"
CLEAN="${4:-}"
GEN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PINNED_HEAD="d12bf2e71eb61d3440bd8f5ed1f937ff33bc9d04"
PINNED_WINDOW_SHA="c52eb30856cbfeb65261bbe97c6b46ef5afa2ba41a00fd48c1b95d9ae7b1ced1"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0

fail() { echo "ORCHESTRATE FAIL: $*" >&2; exit 1; }

# --- enforce pinned inputs (fail-closed) ---
actual_head="$(git -C "$REPO" rev-parse HEAD)"
[ "$actual_head" = "$PINNED_HEAD" ] || fail "HEAD $actual_head != pinned $PINNED_HEAD"
actual_sha="$(sha256sum "$WINDOW" | awk '{print $1}')"
[ "$actual_sha" = "$PINNED_WINDOW_SHA" ] || fail "window.py sha $actual_sha != pinned $PINNED_WINDOW_SHA"

# --- require a clean generated-artifact target ---
GEN_TARGETS=(methods.tsv attributes.tsv internal-calls.tsv external-calls.tsv
             callbacks.tsv counts-manifest.tsv attribute-init-classification.tsv
             checks.txt direct-test-calls.tsv runtime-method-entries.tsv
             test-evidence.md stage3-summary.md test-suite-results.tsv
             run-environment.txt)
existing=0
for t in "${GEN_TARGETS[@]}"; do [ -e "$OUT/$t" ] && existing=1; done
for d in trace-json trace-logs test-suite-logs; do
  [ -d "$OUT/$d" ] && [ -n "$(ls -A "$OUT/$d" 2>/dev/null)" ] && existing=1
done
if [ "$existing" = "1" ]; then
  if [ "$CLEAN" = "--clean" ]; then
    echo "cleaning prior generated targets under $OUT (discrepancies.md preserved)"
    for t in "${GEN_TARGETS[@]}"; do rm -f "$OUT/$t"; done
    rm -rf "$OUT"/trace-json "$OUT"/trace-logs "$OUT"/test-suite-logs
  else
    fail "$OUT already contains generated artifacts; pass --clean to regenerate (discrepancies.md is preserved either way)"
  fi
fi
mkdir -p "$OUT"/{trace-json,trace-logs,test-suite-logs}

echo "=== environment ==="
{
  echo "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host_uname: $(uname -a)"
  echo "python: $(python3 --version 2>&1)"
  echo "python_path: $(command -v python3)"
  echo "repo_HEAD: $actual_head (matches pinned)"
  echo "window_sha256: $actual_sha (matches pinned)"
  echo "PYTHONHASHSEED: $PYTHONHASHSEED"
  echo "PYTHONDONTWRITEBYTECODE: $PYTHONDONTWRITEBYTECODE"
  echo "DISPLAY: ${DISPLAY:-<unset>}"
  echo "WAYLAND_DISPLAY: ${WAYLAND_DISPLAY:-<unset>}"
  echo "CHICKENBUTT_TRANSCRIPT: ${CHICKENBUTT_TRANSCRIPT:-<unset (defaults to webkit)>}"
} | tee "$OUT/run-environment.txt"

echo "=== Stage 1: source inventory ==="
python3 "$GEN/extract.py" "$WINDOW" "$OUT"
python3 "$GEN/checks.py"   "$WINDOW" "$OUT"
python3 "$GEN/direct_calls.py" "$REPO/scripts" "$OUT"

echo "=== Stage 2a: full 15-script suite (normal run, CI order) ==="
# suite scripts may legitimately exit nonzero on a real regression; we record
# each exit code and do NOT abort the orchestrator on a test failure (that is a
# finding, not an orchestration error). `set -e` is suspended only around the
# recorded invocation.
printf "script\texit_code\n" > "$OUT/test-suite-results.tsv"
suite_status=0
n_scripts=0
for f in "$REPO"/scripts/test_*.py; do
  name="$(basename "$f")"
  n_scripts=$((n_scripts+1))
  set +e
  ( cd "$REPO" && python3 "scripts/$name" ) > "$OUT/test-suite-logs/$name.log" 2>&1
  ec=$?
  set -e
  printf "%s\t%s\n" "scripts/$name" "$ec" >> "$OUT/test-suite-results.tsv"
  [ "$ec" -ne 0 ] && suite_status=1
done
[ "$n_scripts" -eq 15 ] || fail "expected 15 test scripts, found $n_scripts"

echo "=== Stage 2b: per-script runtime method-entry tracing (trace failures ARE fatal) ==="
n_traces=0
for f in "$REPO"/scripts/test_*.py; do
  name="$(basename "$f" .py)"
  n_traces=$((n_traces+1))
  set +e
  timeout 120 python3 "$GEN/run_traced.py" "$WINDOW" "$f" \
      "$OUT/trace-json/$name.json" > "$OUT/trace-logs/$name.log" 2>&1
  tec=$?
  set -e
  if [ "$tec" -eq 124 ]; then fail "trace of $name TIMED OUT (exit 124)"; fi
  if [ "$tec" -ne 0 ]; then fail "trace of $name exited nonzero ($tec) -- see trace-logs/$name.log"; fi
  [ -s "$OUT/trace-json/$name.json" ] || fail "trace of $name produced no JSON"
done
[ "$n_traces" -eq 15 ] || fail "expected 15 traces, ran $n_traces"
json_count="$(ls -1 "$OUT"/trace-json/*.json | wc -l)"
[ "$json_count" -eq 15 ] || fail "expected exactly 15 trace JSON files, found $json_count"

python3 "$GEN/aggregate_runtime.py" "$OUT"

echo "=== Stage 2c/3: derived evidence + summaries ==="
python3 "$GEN/test_evidence.py"  "$OUT"
python3 "$GEN/stage3_summary.py" "$OUT"

echo "=== done; suite_status=$suite_status (0 = all 15 passed) ==="
# The orchestrator itself succeeded (all generators + traces ran clean). The
# suite outcome is surfaced via this exit code for the caller to record.
exit "$suite_status"
