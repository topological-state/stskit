# Changelog

## 2.1.6

### Features

- Bahnelementbeschriftung in Gleisbelegung und Streckenfahrplan an der oberen Achse
- Default-Zugschema für neue Regionen in Frankreich und Italien
- Verbesserungen am Streckeneditor
  - Hauptstrecke auswählen
  - Strecke umbenennen
  - Strecke interpolieren (noch nicht voll zuverlässig)
  - Aktualisierung aus Bahnhofeditor
- Verbesserungen am Bahnhofeditor
  - Warnung bei ungespeicherten Änderungen vor Seitenwechsel
  - Nur erlaubte Zuordnungsziele in Auswahlboxen anbieten
 

### Beispielkonfigurationen

- Aaretal
- Arth-Goldau
- Brugg
- Como S.G.
- Emmental
- Entlebuch
- Fribourg
- Gonzen
- Haguenau
- Huttwil
- Kreuzlingen
- Laufental
- Namur
- Obermodern
- Palezieux-Romont
- Romanshorn
- Rovato
- Tarvisio Boscov.
- Venezia S.L.


## 2.1.5

### Features

- Gleisbelegung: Gleise nach Bf-Bft-Bs gruppieren
- Gleisbelegung: Gleise nach Konfiguration (`ordnung`-Attribut) sortieren (im GUI nicht änderbar)
- Default-Bahnhofname von rein numerischen Gleisen ist neu der Stellwerksname (statt _Hbf_)

### Closed issues

- Bahnhofkonfiguration: Fehler beim Zuordnen in eigene Gruppe 

### Beispielkonfigurationen

- Aalter
- Acton Main Line
- Meidling
- Mödling
- Olten
- St. Anton am Arlberg

## 2.1.4

### Features

- Neue Befehle im Streckeneditor: automatische Strecken löschen, Strecke interpolieren ()
- Pushbutton-Aktivierung im Streckeneditor

### Closed issues

- Issue #518: Konfigurationsdatei lädt nicht.

### Beispielkonfigurationen

- Bolzano
- Calanda
- Genève
- Thunersee

Hinweis: Aufgrund der stetigen Entwicklung der Stellwerke können die Beispielkonfigurationen veraltet sein.
  Die Gleisangaben von veralteten Konfigurationen werden so weit wie möglich übernommen,
  müssen aber eventuell manuell angepasst werden.


## 2.1.3

### Features


### Closed issues

- Bahnhofkonfiguration: Konfiguration aus alter Version (1.x) korrekt einlesen
- Streckeneditor: Apply- und Reset-Buttons aktivieren
- Streckeneditor: Automatik-Flag von bearbeiteten und gelöschten Strecken entfernen


## 2.1.2

### Features

- Zugschema Italien: AV, RE, MXP, NCL, RID, INV-Züge

### Closed issues

- Bahnhofkonfiguration: Zuordnung von umbenannten Stammknoten korrekt speichern 
- Führende oder folgende Leerzeichen von Gleisnamen entfernen (Stw Jemeppe)
- Verbesserte Fehlertoleranz im Signalgraph-Import und im Gleisbelegungsfenster


## 2.1.1

### Features

- Durchfahrt mit verzögerter Abfahrtszeit als Fahrzeitreserve beachten.
- Zugschema Italien: MRI und S Züge

### Closed issues

- Issues 155, 156: Freitext-Filterfunktion in Bahnhofeditor
- Hilfeseite zu Einstellungen in Kompilation einpacken 


## 2.1.0

### Features

- Streckeneditor (im Modul Einstellungen)
- Gleissperrung nur noch im Einstellungsfenster einstellbar

### Closed issues

- Fehler beim Laden der Bahnhofkonfiguration
- Pull request 154: Fix gleiseditor checkboxes
- Gleisauswahl bei Aktualisierung nicht zuklappen 


## 2.0.3 - 2.0.8

### Features

- Einheitliche Zugbeschriftung
- Gleisnummern anzeigen in Anschlussmatrix

### Closed issues

- Crash beim Seiten Umschalten im Bildfahrplan
- Issue 153: Attribute Errors in Zugschema
- Issue 152: Anzeigefehler bei Verspätung
- Issue 148: Zugkategorienauswahl
- Issue 149: Werkzeugleiste in Anschlussmatrix
- Issue 151: Fehlende Züge in Anschlussmatrix
- Modulknöpfe im Hauptfenster sperren bis Verbindung steht
- Balkenbeschriftung in Gleisbelegung am oberen Rand
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
