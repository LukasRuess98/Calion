"""Datenanalysen zur Speicherstudie im Fernwärmenetz DHN-A (anonymisiert).

Reproduzierbare Auswertungen außerhalb des Studien-Notebooks auf dem anonymisierten Datensatz ``data/dhn_a/``:

* ``daten``       Laden, Signalprüfungen, korrigierte Erzeugung (GT-Signal, t/h), Kunden-Δp
* ``wetter``      DWD-Stundenwerte (Aktualisierung), Ortszeit, Kältewellen
* ``auslegung``   Auslegungslast aus Tageslast gegen Außentemperatur (Lastgänge 2020–2022, 2025)
* ``anker``       Druckverlust Hauptanlage → Kunden, erforderliche Erzeuger-Δp, Netzhebel, Tracer
* ``run_analyse`` Gesamtlauf, schreibt nach ``results/dhn_study/datenanalyse/``
"""
