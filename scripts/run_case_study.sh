#!/usr/bin/env bash
set -euo pipefail

CONFIGS=("$@")
if [ ${#CONFIGS[@]} -eq 0 ]; then
  CONFIGS=(
    configs/base.yaml
    configs/tech_catalog.yaml
    configs/sites/default.site.yaml
    configs/systems/baseline.system.yaml
    configs/scenarios/pf_then_rh.workflow.scenario.yaml
  )
fi

ARTIFACT_ROOT=${ARTIFACT_ROOT:-artifacts}
TAG=${CASE_TAG:-case_study}
STAMP=$(date +%Y%m%d_%H%M%S)
OUTDIR="${ARTIFACT_ROOT}/${STAMP}_${TAG}"
mkdir -p "${OUTDIR}"

python - <<'PY' "${OUTDIR}" "${CONFIGS[@]}"
import json
import sys
from collections import OrderedDict
from pathlib import Path

from energis.io.exporter import export_scenario_bundle, write_timeseries_csv
from energis.io.plotter import export_plots
from energis.run.rolling_horizon import run_workflow

outdir = Path(sys.argv[1])
config_paths = sys.argv[2:]

workflow = run_workflow(config_paths)

if workflow.rh_result is None and workflow.pf_result is None:
    raise SystemExit("No PF or RH result found – check your configuration")

base_table = workflow.rh_result.table if workflow.rh_result else workflow.pf_result.table  # type: ignore[union-attr]
base_series = workflow.rh_result.series if workflow.rh_result else workflow.pf_result.series  # type: ignore[union-attr]

cost_sections: "OrderedDict[str, OrderedDict[str, float]]" = OrderedDict()
if workflow.pf_result and workflow.pf_result.costs:
    cost_sections["PF"] = OrderedDict((str(k), float(v)) for k, v in workflow.pf_result.costs.items())
if workflow.rh_result and workflow.rh_result.costs:
    cost_sections["RH"] = OrderedDict((str(k), float(v)) for k, v in workflow.rh_result.costs.items())

meta_sections: "OrderedDict[str, OrderedDict[str, object]]" = OrderedDict()
meta_sections["workflow"] = OrderedDict(
    [
        ("steps", list(workflow.plan.steps)),
        ("fix_design", workflow.plan.fix_design),
        ("solver", workflow.config.get("run", {}).get("solver")),
    ]
)
meta_sections["scenario"] = OrderedDict(workflow.config.get("scenario", {}))

input_table = workflow.pf_result.table if workflow.pf_result else base_table  # type: ignore[assignment]
input_section = OrderedDict((col, list(input_table[col])) for col in input_table.columns)
result_section = OrderedDict((name, list(values)) for name, values in base_series.items())

write_timeseries_csv(
    str(outdir / "case_study_timeseries.csv"),
    input_table,
    result_section,
    alternate_path=str(outdir / "case_study_timeseries.dot.csv"),
)

timeseries_sections = [
    {"label": "PF_input", "timestamps": list(input_table.index), "series": input_section},
    {"label": "Workflow_result", "timestamps": list(base_table.index), "series": result_section},
]

design_export = None
if workflow.design is not None:
    design_export = {"heat_pumps": workflow.design.heat_pumps, "storage": workflow.design.storage}

manifest_data = OrderedDict(
    [
        ("workflow_steps", list(workflow.plan.steps)),
        ("slug", outdir.name),
        ("output_directory", str(outdir)),
    ]
)

bundle_paths = export_scenario_bundle(
    str(outdir),
    meta_sections=meta_sections,
    timeseries_sections=timeseries_sections,
    cost_sections=cost_sections,
    design=design_export,
    manifest=manifest_data,
)

plot_files = export_plots(str(outdir), base_table, base_series, workflow.pf_result.summary if workflow.pf_result else None)

with open(outdir / "merged_config.json", "w", encoding="utf-8") as handle:
    json.dump(workflow.config, handle, indent=2)

with open(outdir / "case_study_manifest.json", "w", encoding="utf-8") as handle:
    json.dump(
        {
            "config_paths": config_paths,
            "scenario_bundle": bundle_paths,
            "plots": plot_files,
        },
        handle,
        indent=2,
    )

print(f"Artifacts written to: {outdir}")
PY

