#!/bin/bash
# SB binary-fix-LP sweep, per rung. Plain subshell loop with wait-based concurrency
# (no xargs / no nested bash -c / no export -f -- those fail silently on git-bash-Windows).
cd "$(dirname "$0")/../.." || exit 1
N="${1:-3}"
OUT=output/paper2_sweeps/SB-S1-HK0_binfix
mkdir -p "$OUT"
i=0
for R in 37 73 146 219 292 438 585 731 877 1169 1607 2046; do
  (
    export CALION_ATMOSPHERIC_TES=1
    export CALION_WARMSTART_DUMP=output/uc_seed/SB-S1-HK0/vars_seed.json
    export CALION_WARMSTART_FIXBIN=1
    export CALION_FIXBIN_EXCLUDE="cap_x,hp_sb,EK_SB,HWS_BOILER,HWW_BOILER,P2H_EXISTING"
    export CALION_TES_FIX_MWH="$R"
    export CALION_MIPFOCUS=1
    export CALION_TIMELIMIT=3600
    export PYTHONIOENCODING=utf-8
    export PYTHONPATH=.
    python scripts/paper_2/run_mm_s4_reconcile.py "binfix_SB-S1-HK0_${R}" SB-S1-HK0 > "$OUT/rung_${R}.log" 2>&1
  ) &
  i=$((i+1))
  # throttle to N concurrent
  while [ "$(jobs -rp | wc -l)" -ge "$N" ]; do sleep 20; done
done
wait
echo "DONE_SB_BINFIX_SWEEP"
