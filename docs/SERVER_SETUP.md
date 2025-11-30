# Server-Setup Guide für EnerGIS Notebooks

Diese Anleitung beschreibt, wie die EnerGIS Notebooks auf einem Server ohne grafische Oberfläche ausgeführt werden können.

## 📋 Voraussetzungen

### Minimale Server-Anforderungen

- **Python**: ≥ 3.9
- **RAM**: ≥ 8 GB (empfohlen: 16 GB für große Optimierungen)
- **Disk**: ≥ 5 GB freier Speicher für Workflows und Exports
- **CPU**: Multi-Core empfohlen (Optimierungen können parallelisiert werden)

### Software-Anforderungen

```bash
# JupyterLab/JupyterHub für Notebook-Zugriff
pip install jupyterlab

# EnerGIS Dependencies
pip install panel holoviews bokeh plotly matplotlib pandas numpy

# Solver (z.B. CBC oder Gurobi)
# CBC (Open Source):
sudo apt-get install coinor-cbc  # Linux
# oder Gurobi (Lizenz erforderlich)
```

## 🚀 Setup-Optionen

### Option 1: JupyterLab auf Server (Empfohlen)

JupyterLab bietet die beste Erfahrung mit voller Interaktivität.

#### 1. JupyterLab starten

```bash
# Im Projekt-Verzeichnis
cd /pfad/zu/Planing-Framework-for-Heat

# JupyterLab mit Port-Binding
jupyter lab --ip=0.0.0.0 --port=8888 --no-browser

# Mit SSL (Produktion):
jupyter lab --ip=0.0.0.0 --port=8888 --no-browser \
  --certfile=/pfad/zu/cert.pem \
  --keyfile=/pfad/zu/key.pem
```

#### 2. SSH-Tunnel vom lokalen PC

```bash
# Auf lokalem PC
ssh -L 8888:localhost:8888 user@server-ip

# Dann im Browser öffnen:
# http://localhost:8888
```

#### 3. Notebooks verwenden

Die Notebooks funktionieren **unverändert** über JupyterLab:

```python
# In notebook Zelle 1
from energis.io.notebook_helpers import setup_notebook_environment

# Auto-Detection: Erkennt headless Server automatisch
PROJECT_ROOT = setup_notebook_environment()

# Oder explizit Server-Modus:
PROJECT_ROOT = setup_notebook_environment(server_mode=True)
```

**Panel Dashboards** funktionieren direkt in JupyterLab!

---

### Option 2: Headless Execution (Kein Browser)

Für vollständig automatisierte Ausführung ohne interaktive Dashboards.

#### 1. Notebooks zu Python konvertieren

```bash
# Einzelnes Notebook
jupyter nbconvert --to python notebooks/runner.ipynb

# Alle Notebooks
jupyter nbconvert --to python notebooks/*.ipynb
```

#### 2. Python-Skript anpassen

```python
# runner.py (auto-generiert aus runner.ipynb)

# Setup mit Server-Modus
from energis.io.notebook_helpers import setup_notebook_environment
PROJECT_ROOT = setup_notebook_environment(server_mode=True)

# ... Rest des Codes ...

# Dashboard-Erstellung überspringen oder deaktivieren
# dashboard = create_and_display_dashboard(workflow)  # Auskommentieren
```

#### 3. Ausführen

```bash
python notebooks/runner.py
```

**Ergebnisse** werden trotzdem gespeichert:
- CSV-Exports in `saved_workflows/`
- PDF/SVG-Plots (Matplotlib mit Agg backend)
- Workflow-Pickle für spätere Analyse

---

### Option 3: Panel Server (Remote Dashboard)

Panel kann als eigenständige Web-App deployed werden.

#### 1. Dashboard-Notebook als App

```python
# dashboard_app.ipynb
from energis.io.notebook_helpers import (
    list_saved_workflows,
    load_workflow_from_saved,
    create_and_display_dashboard
)

# Workflows laden
workflows = list_saved_workflows()
latest = workflows[0]  # Neuester Workflow
workflow = load_workflow_from_saved(latest['path'])

# Dashboard erstellen
dashboard = create_and_display_dashboard(workflow, title="EnerGIS Server Dashboard")

# Als servable markieren
dashboard.servable()
```

#### 2. Panel Server starten

```bash
# Einzelnes Notebook
panel serve notebooks/interactive_dashboard.ipynb --port 5006 --allow-websocket-origin='*'

# Produktiv mit HTTPS
panel serve notebooks/interactive_dashboard.ipynb \
  --port 5006 \
  --ssl-certfile=/pfad/zu/cert.pem \
  --ssl-keyfile=/pfad/zu/key.pem \
  --allow-websocket-origin=server.domain.com
```

#### 3. Zugriff

```
https://server-ip:5006/interactive_dashboard
```

---

## 🔧 Server-spezifische Konfiguration

### Matplotlib Backend

Der Code erkennt **automatisch** headless Umgebungen:

```python
# Auto-Detection in setup_notebook_environment():
if not os.environ.get('DISPLAY') and sys.platform != 'win32':
    matplotlib.use('Agg')  # Headless backend
```

**Manuell erzwingen:**

```python
import matplotlib
matplotlib.use('Agg')  # Vor plt import!
import matplotlib.pyplot as plt
```

### Environment Variables

```bash
# Für headless detection
export DISPLAY=""

# JupyterLab Token (Sicherheit)
export JUPYTER_TOKEN="dein-sicheres-token"

# Panel Settings
export PANEL_EMBED=True
export PANEL_EMBED_JSON=True
```

### systemd Service (Auto-Start)

Erstelle `/etc/systemd/system/energis-jupyter.service`:

```ini
[Unit]
Description=EnerGIS JupyterLab Server
After=network.target

[Service]
Type=simple
User=energis-user
WorkingDirectory=/pfad/zu/Planing-Framework-for-Heat
ExecStart=/usr/bin/jupyter lab --ip=0.0.0.0 --port=8888 --no-browser
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Aktivieren:

```bash
sudo systemctl enable energis-jupyter
sudo systemctl start energis-jupyter
sudo systemctl status energis-jupyter
```

---

## 📊 Workflow auf Server

### 1. Optimierung ausführen

```python
# Via JupyterLab oder Python-Skript
from energis.run.rolling_horizon import run_workflow

workflow = run_workflow(config_paths, overrides=...)
```

### 2. Workflow speichern

```python
from energis.io.notebook_helpers import save_workflow_run

workflow_dir = save_workflow_run(
    workflow,
    name="Server Optimization Run",
    description="Automated run on server",
    config_paths=config_paths
)
```

### 3. Ergebnisse abrufen

```bash
# Via SCP vom lokalen PC
scp -r user@server:/pfad/zu/saved_workflows/Workflow_* ./local_results/

# Oder via shared folder (NFS/SMB)
```

### 4. Lokale Analyse

```python
# Auf lokalem PC mit GUI
from energis.io.notebook_helpers import (
    load_workflow_from_saved,
    create_and_display_dashboard
)

workflow = load_workflow_from_saved("./local_results/Workflow_20240101_120000")
dashboard = create_and_display_dashboard(workflow)
dashboard  # Interaktiv im Jupyter
```

---

## 🐛 Troubleshooting

### Problem: "ImportError: cannot import name 'Panel'"

```bash
# Panel installieren
pip install panel holoviews bokeh plotly
```

### Problem: "tkinter.TclError: no display name"

```python
# Matplotlib Backend auf Agg setzen
import matplotlib
matplotlib.use('Agg')
```

Oder in `setup_notebook_environment`:

```python
setup_notebook_environment(server_mode=True)  # Erzwingt Agg backend
```

### Problem: JupyterLab nicht erreichbar

```bash
# Firewall-Port öffnen (Ubuntu/Debian)
sudo ufw allow 8888/tcp

# Port-Status prüfen
netstat -tuln | grep 8888

# JupyterLab Logs
jupyter lab --debug
```

### Problem: Panel Dashboard nicht sichtbar

```python
# In JupyterLab: Panel Extension aktivieren
jupyter labextension install @pyviz/jupyterlab_pyviz

# Oder Panel in iframe mode
import panel as pn
pn.extension(inline=True)
```

### Problem: Solver nicht gefunden

```bash
# CBC installieren (Linux)
sudo apt-get install coinor-cbc

# In Python prüfen
from pyomo.environ import SolverFactory
solver = SolverFactory('cbc')
print(solver.available())  # Sollte True sein
```

---

## 📚 Best Practices

### 1. Automatisierte Runs

Erstelle Cron-Jobs für regelmäßige Optimierungen:

```bash
# crontab -e
0 2 * * * cd /pfad/zu/Planing-Framework-for-Heat && python scripts/automated_run.py
```

### 2. Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/energis/runs.log'),
        logging.StreamHandler()
    ]
)
```

### 3. Resource Monitoring

```bash
# CPU/RAM während Optimierung
htop

# Disk usage
du -sh saved_workflows/

# Logs
tail -f /var/log/energis/runs.log
```

### 4. Backup

```bash
# Workflows sichern
rsync -av saved_workflows/ backup-server:/backups/energis/

# Configs versionieren
git add configs/
git commit -m "Update production configs"
```

---

## ✅ Zusammenfassung

| Feature | JupyterLab | Headless | Panel Server |
|---------|------------|----------|--------------|
| **Interaktive Dashboards** | ✅ | ❌ | ✅ |
| **Notebook-Bearbeitung** | ✅ | ❌ | ❌ |
| **Auto-Export (CSV/PDF)** | ✅ | ✅ | ✅ |
| **Remote-Zugriff** | ✅ (SSH Tunnel) | ❌ | ✅ (direkt) |
| **Automatisierung** | ⚠️ (manuell) | ✅ | ⚠️ |
| **Setup-Komplexität** | Niedrig | Sehr niedrig | Mittel |

**Empfehlung:**
- **Development**: JupyterLab mit SSH-Tunnel
- **Production/Automation**: Headless Python-Skripte
- **Stakeholder Dashboards**: Panel Server

---

## 🆘 Support

Bei Problemen:

1. Logs prüfen: `jupyter lab --debug`
2. Python-Environment: `pip list | grep -E "panel|jupyter|matplotlib"`
3. Issue öffnen: [GitHub Issues](https://github.com/LukasRuess98/Planing-Framework-for-Heat/issues)

---

**Letzte Aktualisierung:** 2024-11-30
