#!/usr/bin/env bash
# AC-block launcher (2026-10-19): isolated, single SB-S1/S2/S3 solve with AC1/AC2 env overrides.
# usage: ac_run.sh <tag> <scenario_id> <warmstart_dir|-> [KEY=VAL ...]
# Output isolated under output/_ac/<tag>/ (CALION_OUT_BASE, logs, solfiles, nodefiles) so nothing
# in output/v7_final or other campaigns can be clobbered (feedback_scenario_id_clobbering).
set -u
TAG="$1"; SCEN="$2"; WS="$3"; shift 3
cd "$(dirname "$0")/../.."
BASE="output/_ac/${TAG}"
mkdir -p "${BASE}/paper2_runs" "${BASE}/nodefiles"
export PYTHONIOENCODING=utf-8
export CALION_OUT_BASE="${BASE}/paper2_runs"
export CALION_MIPFOCUS=3 CALION_MIPGAP=0.0015 CALION_TIMELIMIT="${CALION_TIMELIMIT:-172800}"
[ "$WS" != "-" ] && export CALION_WARMSTART_FROM="$WS"
for kv in "$@"; do export "$kv"; done
echo "=== AC JOB ${TAG} scen=${SCEN} ws=${WS} env: $* (started $(date '+%F %T')) ==="
python -m scripts.paper_2.scenario_runner -s "${SCEN}" -g "${AC_THREADS:-22}"
echo "=== AC JOB ${TAG} finished rc=$? ($(date '+%F %T')) ==="
