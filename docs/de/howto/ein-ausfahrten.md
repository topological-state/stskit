# Ein-/Ausfahrten

Das Einfahrts- und Ausfahrtsdiagramm zeigt die Belegung der Ein- und Ausfahrtsgleise.

Die Fahrpläne im Stellwerksim haben keine definierten Einfahrts- und Ausfahrtszeiten.
Stattdessen zeigen die Fahrpläne die Ankunft/Abfahrt des nächsten Fahrplanpunkts.
stskit extrapoliert die Einfahrts- und Ausfahrtszeit anhand gemesser Fahrzeiten.

![stskit-screen-einausfahrten](https://user-images.githubusercontent.com/51272421/210151702-598b9268-4cd7-4703-9769-4e136fd240f3.png)

## Markierungen

- Gleisbelegung (nur Ein- und Ausfahrten) in Balkendarstellung
  - Pfeil links zeigt Einfahrt, rechts Ausfahrt
  - Linie zeigt Verspätung (max. 15 Minuten)
  - Farbschema ist noch fest eingestellt, wird später einstellbar gemacht werden
- Konflikte: gestrichelter Rahmen
  - gleichzeitig ein-/ausfahrende Züge (rot)
  - Löschung durch Fdl (grau)
- Zuginfo

## Werkzeuge

- Einstellungsseite
  - Gleisauswahl
- Filter: nur benutzte Gleise anzeigen
- Markierung
  - Konflikt
  - löschen
  - zurücksetzen

Für Zuginfo, Zug anklicken.
Alle in einem Konflikt stehende Züge werden aufgelistet
Es können mehr als zwei Slots ausgewählt sein!
Auf den Hintergrund klicken, um die Auswahl aufzuheben.

## Bemerkungen

Ein- und Ausfahrten werden intern wie Gleise gehandhabt.
Wenn in einem Stellwerk wie im Beispiel oben eine Einfahrt den gleichen Namen wie ein Gleis hat, 
werden beide dargestellt und mit einer Warnung versehen.
