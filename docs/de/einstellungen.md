# Einstellungen


Wenn die automatische Konfiguration in einem Stellwerk nicht richtig funktioniert, kann sie hier korrigiert werden.

- Zuerst die Anschlüsse und Bahnhöfe konfigurieren, danach die Strecken.
- Nach grösseren Änderungen oder vor einem Seitenwechsel *Anwenden* oder *OK* klicken.
- Es gibt kein Undo. *Zurücksetzen* verwirft die nicht gespeichterten Aenderungen.

## Anschlüsse und Bahnhöfe

Die Pluginschnittstelle von Stellwerksim übermittelt nur Gleisnamen, keine Bahnhofsnamen.
stsDispo kennt zudem noch die Kategorien Bahnsteig und Bahnhofteil.
In vielen Stellwerken können diese Elemente automatisch aus den Gleisnamen abgeleitet werden.
Die Dialogseiten Anschlüsse und Bahnhöfe zeigen diese Zuordnung an und ermöglichen es, die Zuordnung zu bearbeiten.

Das zugrunde liegende Bahnhofmodell und die Bedienung des Editors werden unter
[Anschlüsse und Bahnhöfe](bahnhofdefinition.md) beschrieben.


## Streckendefinition

Die Bedienung des Streckeneditors wird unter
[Streckendefinition](streckendefinition.md) beschrieben.


## Zugschema

Das Zugschema für das laufende Stellwerk aus der Liste auswählen.
Die Bearbeitung der Zugschemata ist nur über Konfigurationsdateien möglich.


## Persistenz

Die hier gemachten Einstellungen werden beim Beenden des Programms in einer Konfigurationsdatei im JSON-Format gespeichert.
Die Konfigurationsdatei befindet sich im Home-/User-Verzeichnis unter `.stskit`.
Der Dateiname entspricht der Anlagennummer im Stellwerksim.

Die Konfigurationsdateien können nach dem Umbau eines Stellwerks fehlerhaft werden.
Im Extremfall muss die entsprechende Konfigurationsdatei manuell gelöscht werden.
