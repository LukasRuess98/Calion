# 🔍 Dashboard Kompatibilitätsprüfung

Dieses Dokument erklärt, wie Sie prüfen können, ob das Dashboard in VS Code und im Browser korrekt funktioniert.

## ✅ Schnelle Kompatibilitätsprüfung

Führen Sie das Prüfskript aus:

```bash
python check_dashboard_compatibility.py
```

Das Skript überprüft:
- ✅ Alle erforderlichen Dependencies (Panel, Plotly, Holoviews, Bokeh)
- ✅ Panel Extensions (plotly, tabulator)
- ✅ Widget-Kompatibilität (Tabulator, Plotly, Select, MultiChoice)
- ✅ Dashboard-Module können importiert werden
- ✅ Gespeicherte Workflows vorhanden
- ✅ Umgebung (VS Code, Jupyter, Display)

---

## 🎯 Kompatibilität: VS Code vs Browser

### ✅ Was funktioniert in beiden?

| Feature | VS Code | Browser (Panel Server) |
|---------|---------|------------------------|
| **Interaktive Plots** | ✅ | ✅ |
| **Tabulator-Tabellen** | ✅ | ✅ |
| **Multi-Select Widgets** | ✅ | ✅ |
| **Zeitbereich-Slider** | ✅ | ✅ |
| **Zoom/Pan/Hover** | ✅ | ✅ |
| **Export (PNG)** | ✅ | ✅ |
| **Auto-Reload** | ⚠️ manuell | ✅ automatisch |
| **Multi-User** | ❌ | ✅ |

### VS Code (Jupyter Extension)

**Vorteile:**
- ✅ Schneller Start (kein Server)
- ✅ Integriert in IDE
- ✅ Code und Dashboard in einer Ansicht
- ✅ Direkter Zugriff auf Variablen

**Limitierungen:**
- ⚠️ Manchmal langsamer Rendering
- ⚠️ Neustart bei Extension-Updates nötig
- ❌ Kein Multi-User Support

**Setup:**
1. Öffne `notebooks/interactive_dashboard.ipynb` in VS Code
2. Führe alle Zellen aus
3. Dashboard wird inline angezeigt

**Troubleshooting VS Code:**
```python
# Falls Dashboard nicht angezeigt wird:
# Option 1: Kernel neu starten
# Kernel: Restart

# Option 2: Panel Extension neu laden
import panel as pn
pn.extension('plotly', 'tabulator', sizing_mode='stretch_width')

# Option 3: Inline-Modus erzwingen (nur wenn nötig)
pn.extension('plotly', 'tabulator', inline=True)
```

---

### Browser (Panel Server)

**Vorteile:**
- ✅ Beste Performance
- ✅ Volle Funktionalität
- ✅ Multi-User fähig
- ✅ Auto-Reload bei Code-Änderungen
- ✅ Zugriff von jedem Gerät im Netzwerk

**Limitierungen:**
- ⚠️ Benötigt Panel Server
- ⚠️ Port muss frei sein

**Setup:**
```bash
# Lokal (öffnet automatisch Browser)
./start_dashboard.sh

# Server (Netzwerk-Zugriff)
./start_dashboard_server.sh

# Manuell
panel serve notebooks/interactive_dashboard.ipynb --show
```

**Troubleshooting Browser:**
```bash
# Problem: "Connection refused"
# Lösung: Prüfe ob Server läuft
lsof -i :5006

# Problem: "Port already in use"
# Lösung: Anderer Port
./start_dashboard.sh 5007

# Problem: "WebSocket connection failed"
# Lösung: Korrekte Origin setzen
panel serve ... --allow-websocket-origin='*'
```

---

## 🔧 Behobene Kompatibilitätsprobleme

### Problem 1: Tabulator-Widget nicht geladen

**Symptom:**
```
Tabulator tables are not displayed or show as empty
```

**Ursache:**
Panel Extension lud nur 'plotly', nicht 'tabulator'

**Fix (bereits implementiert):**
```python
# Vorher:
pn.extension('plotly', sizing_mode='stretch_width')

# Nachher (KORREKT):
pn.extension('plotly', 'tabulator', sizing_mode='stretch_width')
```

**Dateien geändert:**
- ✅ `energis/io/dashboard.py` (Zeile 80)
- ✅ `notebooks/interactive_dashboard.ipynb` (Cell 3)

---

### Problem 2: WebSocket Origin bei externem Zugriff

**Symptom:**
```
WebSocket connection to 'ws://server-ip:5006/ws' failed
```

**Ursache:**
Panel Server akzeptiert standardmäßig nur localhost

**Fix:**
```bash
# In start_dashboard_server.sh
panel serve ... --allow-websocket-origin="*"
```

Alternativ für spezifische Origins:
```bash
panel serve ... --allow-websocket-origin="server.domain.com" \
                --allow-websocket-origin="192.168.1.100"
```

---

### Problem 3: VS Code zeigt Panel nicht an

**Symptom:**
- Dashboard-Code läuft ohne Fehler
- Aber keine Anzeige in VS Code

**Mögliche Ursachen & Lösungen:**

1. **Jupyter Extension veraltet**
   ```bash
   # VS Code: Extensions → Jupyter → Update
   ```

2. **Panel Extension nicht geladen**
   ```python
   # In erster Zelle des Notebooks:
   import panel as pn
   pn.extension('plotly', 'tabulator', sizing_mode='stretch_width')
   ```

3. **Kernel-Neustart nötig**
   - `Ctrl+Shift+P` → "Jupyter: Restart Kernel"

4. **Inline-Modus aktivieren** (selten nötig)
   ```python
   pn.extension('plotly', 'tabulator', inline=True)
   ```

---

## 📊 Getestete Konfigurationen

### ✅ Funktioniert garantiert:

| Setup | OS | Browser/IDE | Status |
|-------|----|-----------| -------|
| **Localhost Panel Server** | Linux | Chrome 120+ | ✅ |
| **Localhost Panel Server** | Linux | Firefox 120+ | ✅ |
| **Localhost Panel Server** | Windows | Chrome 120+ | ✅ |
| **VS Code Jupyter** | Linux | VS Code 1.85+ | ✅ |
| **VS Code Jupyter** | Windows | VS Code 1.85+ | ✅ |
| **JupyterLab** | Linux | Any Browser | ✅ |
| **Server Panel (SSH)** | Linux Server | SSH Tunnel | ✅ |
| **Server Panel (LAN)** | Linux Server | LAN Access | ✅ |

### ⚠️ Bekannte Einschränkungen:

| Setup | Einschränkung | Workaround |
|-------|--------------|------------|
| VS Code Remote SSH | Langsam bei großen Dashboards | Panel Server nutzen |
| Safari < 16 | WebSocket Issues | Chrome/Firefox nutzen |
| Mobile Browser | UI zu klein | Desktop empfohlen |

---

## 🧪 Manuelle Tests

### Test 1: Dependencies
```bash
python -c "import panel, holoviews, plotly, bokeh; print('✅ OK')"
```

### Test 2: Panel Extension
```python
import panel as pn
pn.extension('plotly', 'tabulator')
print('✅ Extensions loaded')
```

### Test 3: Tabulator Widget
```python
import panel as pn
import pandas as pd

df = pd.DataFrame({'A': [1, 2, 3]})
table = pn.widgets.Tabulator(df)
print('✅ Tabulator works')
```

### Test 4: Plotly Pane
```python
import panel as pn
import plotly.graph_objects as go

fig = go.Figure()
fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
pane = pn.pane.Plotly(fig)
print('✅ Plotly works')
```

### Test 5: Dashboard Module
```python
from energis.io.dashboard import create_dashboard, HAVE_PANEL
print(f'HAVE_PANEL: {HAVE_PANEL}')
```

---

## 🔄 Automatische Kompatibilitätsprüfung

Das Skript `check_dashboard_compatibility.py` führt alle Tests automatisch aus:

```bash
python check_dashboard_compatibility.py
```

**Beispiel-Output:**
```
==============================================================
  🎛️  EnerGIS Dashboard Compatibility Check
==============================================================

📦 Dependency Check
✅ Panel version 1.3.8 installed
✅ Holoviews version 1.18.1 installed
✅ Plotly version 5.18.0 installed
✅ Bokeh version 3.3.2 installed
✅ Pandas version 2.1.4 installed

🔧 Panel Extension Check
Testing 'plotly' extension...
✅ Plotly extension loaded
Testing 'tabulator' extension...
✅ Tabulator extension loaded
Testing combined extensions...
✅ Combined extensions loaded successfully

🎛️ Widget Compatibility Check
Testing Tabulator widget...
✅ Tabulator widget works
Testing Plotly pane...
✅ Plotly pane works
...

📋 Summary
   Dependencies         ✅ PASS
   Extensions          ✅ PASS
   Widgets             ✅ PASS
   Dashboard           ✅ PASS
   Workflows           ✅ PASS
   Environment         ✅ PASS

==============================================================
  ✅ All checks passed! Dashboard is ready to use.
==============================================================
```

---

## 💡 Best Practices

### Für Entwicklung (VS Code)
1. Öffne `notebooks/interactive_dashboard.ipynb`
2. Führe Setup-Zellen aus (1-4)
3. Wähle Workflow (Zelle 8)
4. Erstelle Dashboard (Zelle 12)
5. Bei Problemen: Kernel neu starten

### Für Präsentationen (Browser)
1. Starte Panel Server: `./start_dashboard.sh`
2. Browser öffnet automatisch
3. Dashboard ist schneller und stabiler
4. Mehrere Tabs/Fenster möglich

### Für Server/Remote
1. Starte Server-Modus: `./start_dashboard_server.sh`
2. Oder SSH-Tunnel: `ssh -L 5006:localhost:5006 user@server`
3. Firewall-Port öffnen: `sudo ufw allow 5006/tcp`
4. Zugriff von jedem PC im Netzwerk

---

## 📚 Weiterführende Dokumentation

- **Dashboard Features:** `docs/DASHBOARD.md`
- **Server Setup:** `docs/SERVER_SETUP.md`
- **Schnellstart:** `DASHBOARD_START.md`
- **Panel Docs:** https://panel.holoviz.org

---

## 🐛 Häufige Fehler & Lösungen

### Fehler: "No module named 'panel'"
```bash
pip install panel holoviews bokeh plotly
```

### Fehler: "Tabulator not displaying"
```python
# Stelle sicher, dass Extension geladen ist:
pn.extension('plotly', 'tabulator', sizing_mode='stretch_width')
```

### Fehler: "Port 5006 already in use"
```bash
# Anderen Port verwenden:
./start_dashboard.sh 5007
```

### Fehler: "WebSocket connection failed"
```bash
# Server mit korrekter Origin starten:
panel serve ... --allow-websocket-origin='*'
```

### Fehler: "Dashboard blank in VS Code"
```python
# Kernel neu starten und erneut ausführen
# Oder inline-Modus:
pn.extension('plotly', 'tabulator', inline=True)
```

---

**Stand:** 2024-11-30
**Getestete Versionen:**
- Panel: 1.3.x
- Plotly: 5.18.x
- Holoviews: 1.18.x
- Bokeh: 3.3.x
