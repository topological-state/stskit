# Changelog

## 2.0.8

### Closed issues

- Crash beim Seiten Umschalten im Bildfahrplan

## 2.0.7

### Closed issues

- Issue 153: Attribute Errors in Zugschema

## 2.0.6

### Features

- Einheitliche Zugbeschriftung
- Gleisnummern anzeigen in Anschlussmatrix

### Closed issues

- Issue 152: Anzeigefehler bei Verspätung

## 2.0.5

### Closed issues

- Issue 148: Zugkategorienauswahl
- Issue 149: Werkzeugleiste in Anschlussmatrix
- Issue 151: Fehlende Züge in Anschlussmatrix
- Modulknöpfe im Hauptfenster sperren bis Verbindung steht
- Balkenbeschriftung in Gleisbelegung am oberen Rand

## 2.0.3 (2025-06-29)

### Closed issues

- Issue 144: Runtime Error
- Issue 145: Anschlussmatrix

## 2.0.1 (2025-06-28)

### Features

- Graphbasiertes Datenmodell für alle Zugläufe unter Berücksichtigung von Bereitstellungsvorgängen und Fdl-Korrekturen.
- Graphbasierter Verspätungsalgorithmus.
- Verbesserte Gleisidentifikation und strikte Trennung von Anschluss- und Bahnhofgleisen.
- Verbesserte Darstellung von Bereistellungsvorgängen (Kuppeln/Flügeln/Nummernwechsel).
- Neues Modul Rangiertabelle.
- Anschlussmatrix: überarbeitete Grafik.
- Bildfahrplan: überarbeitete Grafik mit Darstellung von Bereitstellungsvorgängen und Abhängigkeiten.
- Gleisbelegung: Warnung bei falscher Kupplungsreihenfolge.
- Integrierter Editor für Anlagenkonfiguration.
- Einfacheres Deployment: 
  - uv-Paketmanager für Quellcode
  - Ausführbare Dateien mittels nuitka und GitHub-Actions
 
### Breaking changes

- Das neue Schema der Konfigurationsdateien ist inkompatibel zu der Version 1. 
Bestehende Konfigurationsdaten werden automatisch migriert, können nachher aber nicht mehr in Version 1 benutzt werden.
- (intern) Grosses Refactoring der Modulstruktur, konsequente Separation von Modell und View.
