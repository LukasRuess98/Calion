# Junction-Based Network Config Design

**Date:** 2026-04-16  
**Status:** Approved  
**Scope:** Memmingen L3 + Framework-weite Änderung

---

## Ziel

Das Netz wird vollständig über **Junctions + Rohre** abgebildet. Jede Junction
kann Erzeuger (Assets) und/oder Verbraucher (Demands) tragen. Der bisherige
`type: producer/consumer/junction`-Pflichtschlüssel entfällt — die Rolle wird
aus den vorhandenen Keys abgeleitet.

---

## YAML Config Schema

### Neues `nodes:`-Format

```yaml
nodes:
  # Erzeuger-Junction (hat assets)
  E_1:
    assets: [boiler_main, tes_main]

  # Reine Routing-Junctions
  j_1: {}
  j_2: {}

  # Verbraucher-Junction, ein Consumer
  V_1:
    consumers:
      - column: "V_1_demand_MWth"

  # Verbraucher-Junction, mehrere Consumer (einzelne Zeitreihen)
  V_X:
    consumers:
      - column: "V_X_demand_MWth"
      - column: "V_X2_demand_MWth"

  # Gemischte Junction (lokales BHKW + eigene Last)
  J_mixed:
    assets: [local_chp]
    consumers:
      - column: "local_demand_MWth"
```

### Rollenableitung

| Keys vorhanden | Abgeleitete Rolle | Interner `type` |
|---|---|---|
| nur `assets` | Erzeuger | `producer` |
| nur `consumers` | Verbraucher | `consumer` |
| `assets` + `consumers` | Gemischt | `mixed` |
| keines | Reines Routing | `junction` |

Explizites `type:` bleibt als optionaler Override erhalten.

### Consumer-Definition (inline, pro Junction)

Jeder Consumer in der Liste hat:
- `column` (Pflicht): Spaltenname in der Input-Tabelle
- Künftig erweiterbar: `name`, `peak_mw`, `return_temp_c`, etc.

### Alle Junctions explizit

Reine Routing-Junctions stehen immer explizit in `nodes:` (auch wenn leer),
um spätere Erweiterungen zu ermöglichen.

---

## Memmingen L3 — Vorher/Nachher

**Vorher:**
```yaml
nodes:
  E_1:
    type: producer
    assets: [boiler_main, tes_main]
  j_1:
    type: junction
  V_1:
    type: consumer
    demand:
      column: "V_1_demand_MWth"
```

**Nachher:**
```yaml
nodes:
  E_1:
    assets: [boiler_main, tes_main]
  j_1: {}
  V_1:
    consumers:
      - column: "V_1_demand_MWth"
```

---

## Code-Änderungen

### `calion/models/network_manager.py`

**`_parse_nodes()`** — Rollenableitung:
```python
def _infer_node_type(node_cfg: dict) -> str:
    has_assets = bool(node_cfg.get('assets'))
    has_consumers = bool(node_cfg.get('consumers'))
    if has_assets and has_consumers:
        return 'mixed'
    if has_assets:
        return 'producer'
    if has_consumers:
        return 'consumer'
    return 'junction'
```

Explizites `type:` als Override: wird gesetzt, falls im YAML vorhanden,
sonst `_infer_node_type()` aufgerufen.

### Demand-Loading (`unified_config.py` oder `system_builder.py`)

Für `consumers`-Liste: je Consumer einen eigenen Pyomo Param anlegen:
```
heatd_{node_id}_0   ← consumers[0].column
heatd_{node_id}_1   ← consumers[1].column
```

Legacy `demand.column` wird intern zu `consumers: [{column: ...}]` konvertiert.

### `calion/models/blocks/thermal_node.py`

Neuer Pfad für `consumers`-Liste:
- N × `{PREFIX}_Q_demand_{i}` Params (je Timeseries)
- N × `{PREFIX}_m_dot_demand_{i}` Vars
- Massenstrombilanz: `Σ m_dot_in = Σ m_dot_out + Σ m_dot_demand_i`
- Wärmebilanz je Consumer: `Q_demand_i = m_dot_demand_i × cp × ΔT`
- `mixed`-Typ: Producer-Logik (Assets verknüpfen) + Consumer-Logik (Demands) kombiniert

### `calion/run/utilities/validation.py`

- `type:`-Pflichtfeld-Check entfernen
- `consumers:` und `assets:` als gültige Rollenindikatoren akzeptieren
- Warnung wenn weder `type` noch `consumers`/`assets` vorhanden (reines Routing → OK)

---

## Rückwärtskompatibilität

| Altes Format | Verhalten |
|---|---|
| `type: producer` + `assets: [...]` | Funktioniert — `type` als Override erkannt |
| `type: consumer` + `demand: {column: ...}` | Intern zu `consumers: [{column: ...}]` konvertiert |
| `type: junction` | Weiterhin reines Routing |

Bestehende Configs laufen ohne Anpassung weiter. Migration ist optional.

---

## Ergebnisstruktur

Junction-Temperaturen/Drücke auf Node-Ebene, Consumer-Demands darunter:

```json
"nodes": {
  "V_1": {
    "type": "consumer",
    "consumers": [
      {
        "index": 0,
        "column": "V_1_demand_MWth",
        "Q_demand_mw": [...],
        "total_demand_mwh": 42.3,
        "peak_demand_mw": 3.1
      }
    ],
    "T_supply_c": [...],
    "T_return_c": [...]
  }
}
```

---

## Was nicht geändert wird

- `assets:`-Top-Level-Sektion: identisch
- Pipe-Format: unverändert
- Temperatur-Linearisierung / PWL / MILP-Logik: unverändert
- Ergebnis-Exports: erweitert, nicht ersetzt

---

## Nicht im Scope

- Umbenennung bestehender Node-IDs (E_1, V_1..V_27, j_1..j_7 bleiben)
- Änderungen an Pipe-Parametern oder Asset-Definitionen
- Neue Physik-Modelle
