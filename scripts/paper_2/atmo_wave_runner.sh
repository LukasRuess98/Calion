#!/bin/bash
# Controlled-concurrency atmospheric fixed-rung sweep runner.
# Reads task lines "SCEN RUNG SEED" (SEED=none or a dump path) from $1; runs N in parallel.
# Each task: TES fixed at RUNG, atmospheric config, MIPFocus=1, 2h cap; optional MIP-start seed.
# Usage: bash atmo_wave_runner.sh tasks.txt [N]
TASKS="$1"; N="${2:-7}"
cd "$(dirname "$0")/../.." || exit 1
cat "$TASKS" | xargs -P "$N" -L1 bash -c '
  scen="$0"; R="$1"; seed="$2"
  d="output/paper2_sweeps/${scen}_atmo2"; mkdir -p "$d"
  export CALION_ATMOSPHERIC_TES=1 CALION_TES_FIX_MWH="$R" CALION_MIPFOCUS=1 CALION_TIMELIMIT=7200 PYTHONIOENCODING=utf-8 PYTHONPATH=.
  if [ "$seed" != "none" ]; then export CALION_WARMSTART_DUMP="$seed"; fi
  python scripts/paper_2/run_mm_s4_reconcile.py "atmo2_${scen}_${R}" "$scen" > "$d/rung_${R}.log" 2>&1
'
echo "DONE_ATMO_WAVE $TASKS"
