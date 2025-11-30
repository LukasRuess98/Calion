# 🎛️ Dashboard im Browser starten

Das EnerGIS Dashboard kann einfach im Browser über localhost gestartet werden!

## 🚀 Schnellstart

### Für lokale Nutzung (VS Code / Ihr PC):

```bash
./start_dashboard.sh
```

Das Dashboard öffnet sich automatisch im Browser unter:
**http://localhost:5006/interactive_dashboard**

### Für Server (Remote-Zugriff):

```bash
./start_dashboard_server.sh
```

Dashboard ist dann erreichbar unter:
- **Lokal:** http://localhost:5006/interactive_dashboard
- **Von anderen PCs:** http://[SERVER-IP]:5006/interactive_dashboard

---

## 📋 Voraussetzungen

Einmalig Dependencies installieren:

```bash
pip install panel holoviews bokeh plotly
```

---

## 🎯 Nutzungsszenarien

### 1️⃣ Lokale Entwicklung (Ihr PC)

```bash
# Standard-Start
./start_dashboard.sh

# Anderer Port (falls 5006 belegt)
./start_dashboard.sh 5007
```

✅ **Vorteile:**
- Öffnet automatisch Browser
- Auto-Reload bei Änderungen
- Nur lokal erreichbar (sicher)

---

### 2️⃣ Server-PC (Remote Dashboard)

```bash
# Dashboard auf Server starten
./start_dashboard_server.sh

# Mit anderem Port
./start_dashboard_server.sh 5007
```

✅ **Vorteile:**
- Von jedem PC im Netzwerk erreichbar
- Optimierung läuft auf Server (mehr Rechenpower)
- Mehrere Nutzer können gleichzeitig zugreifen

🔧 **Firewall-Port öffnen:**
```bash
sudo ufw allow 5006/tcp
```

📍 **Zugriff von Ihrem PC:**
```
http://SERVER-IP:5006/interactive_dashboard
```
Ersetzen Sie `SERVER-IP` mit der IP-Adresse Ihres Servers (z.B. `192.168.1.100`)

---

### 3️⃣ SSH-Tunnel (sicher über Internet)

Falls Sie von außen auf einen Server zugreifen:

```bash
# Auf Ihrem lokalen PC
ssh -L 5006:localhost:5006 user@server-ip

# Dann im Browser öffnen:
# http://localhost:5006/interactive_dashboard
```

---

## 🎨 Dashboard-Features

Nach dem Start:

1. **📊 Overview Tab**
   - KPI-Cards mit Kosten, CAPEX, Wärmebedarf
   - Zusammenfassung und Jahresübersicht

2. **📈 Zeitreihen Tab** (INTERAKTIV!)
   - Komponenten auswählen mit Multi-Select
   - Zeitbereich mit Slider anpassen
   - Plot-Typ wechseln (Stacked Area, Lines, Bars)
   - Zoom, Pan, Hover für Details

3. **💰 Kosten Tab**
   - Breakdown der Kostenblöcke
   - Interaktive sortierbare Tabelle
   - Top-3 Zusammenfassung

4. **🏭 Design Tab**
   - Anlagenkapazitäten
   - Design-Tabelle
   - JSON-Export

5. **🔀 Vergleich Tab**
   - PF vs RH/MPC Vergleich
   - Optimality Gap Analyse

---

## 🛠️ Alternativen

### Direkt mit Panel-Befehl:

```bash
# Lokal
panel serve notebooks/interactive_dashboard.ipynb --show

# Server (externe Zugriffe)
panel serve notebooks/interactive_dashboard.ipynb --address 0.0.0.0 --port 5006
```

### In JupyterLab:

Öffnen Sie `notebooks/interactive_dashboard.ipynb` in JupyterLab und führen Sie die Zellen aus. Das Dashboard wird direkt im Notebook angezeigt.

---

## 🐛 Troubleshooting

### Problem: "Port already in use"
```bash
# Anderen Port verwenden
./start_dashboard.sh 5007
```

### Problem: "Panel not found"
```bash
# Dependencies installieren
pip install panel holoviews bokeh plotly
```

### Problem: Dashboard im Browser nicht sichtbar

1. Prüfen Sie die Terminal-Ausgabe auf Fehler
2. Prüfen Sie ob Port erreichbar ist:
   ```bash
   lsof -i :5006
   ```
3. Firewall prüfen (bei Server):
   ```bash
   sudo ufw status
   sudo ufw allow 5006/tcp
   ```

### Problem: Keine Workflows gefunden

Das Dashboard zeigt gespeicherte Workflows an. Erstellen Sie zuerst einen:
1. Öffnen Sie `notebooks/runner.ipynb` oder `notebooks/scenario_studio.ipynb`
2. Führen Sie eine Optimierung aus
3. Der Workflow wird automatisch in `saved_workflows/` gespeichert

---

## 📊 Workflow

```
┌─────────────────────────────────────────────────┐
│ 1. Optimierung ausführen                        │
│    (runner.ipynb, scenario_studio.ipynb)        │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 2. Workflow wird gespeichert                    │
│    saved_workflows/Workflow_YYYYMMDD_HHMMSS/    │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 3. Dashboard starten                            │
│    ./start_dashboard.sh                         │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 4. Im Browser analysieren                       │
│    http://localhost:5006/interactive_dashboard  │
└─────────────────────────────────────────────────┘
```

---

## 💡 Tipps

### Performance für große Datensätze
Falls die Optimierung sehr viele Zeitschritte hat (>10.000):
- Dashboard lädt trotzdem schnell
- Nutzen Sie den Zeitbereich-Slider im Zeitreihen-Tab
- Wählen Sie nur relevante Komponenten aus

### Mehrere Dashboards parallel
Sie können mehrere Dashboards auf verschiedenen Ports starten:
```bash
./start_dashboard.sh 5006 &
./start_dashboard.sh 5007 &
./start_dashboard.sh 5008 &
```

### Als permanenter Service (Linux Server)
Siehe `docs/SERVER_SETUP.md` für systemd-Service-Setup.

---

## ✅ Zusammenfassung

| Methode | Befehl | Zugriff | Verwendung |
|---------|--------|---------|------------|
| **Lokal** | `./start_dashboard.sh` | localhost | Entwicklung, lokale Analyse |
| **Server** | `./start_dashboard_server.sh` | Netzwerk-IP | Team-Zugriff, Server-Optimierungen |
| **SSH-Tunnel** | `ssh -L 5006:localhost:5006 ...` | localhost (via SSH) | Sicherer Remote-Zugriff |
| **JupyterLab** | Notebook öffnen + ausführen | JupyterLab | Integrierte Entwicklung |

---

**🎉 Viel Erfolg mit dem Dashboard!**

Bei Fragen: Siehe `docs/DASHBOARD.md` für detaillierte Dokumentation
