# outputs/

Runtime-generated output files. All subdirectories are listed in `.gitignore`
and will not be committed to version control.

| Directory    | Contents |
|-------------|----------|
| `runs/`      | Per-run results: CSV timeseries, PDF/SVG plots, solver SOL files |
| `workflows/` | Saved notebook workflows (pickle + metadata.json) |
| `dashboard/` | Dashboard exports and state files |

## Migration from legacy paths

If you have existing data in `exports/`, `results/`, `notebooks/saved_workflows/`,
or `saved_workflows/`, migrate it with:

```bash
python scripts/migrate_outputs.py --dry-run   # preview
python scripts/migrate_outputs.py             # move
python scripts/migrate_outputs.py --copy      # copy instead of move
```
