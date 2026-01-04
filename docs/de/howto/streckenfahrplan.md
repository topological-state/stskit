# Streckenfahrplan

Der Streckenfahrplan oder Bildfahrplan zeigt die Zugläufe unter Berücksichtigung der Verspätungslage in einem Weg-Zeit-Diagramm an.

![stskit-screen-bildfahrplan](https://user-images.githubusercontent.com/51272421/210151679-8072be36-dbc6-4d4b-b388-a4ec940e5cf9.png)

## Markierungen

- Ausgezogene Linie: Fahrten zwischen Bahnhöfen
- Gestrichelte Linie: Wartezeiten und Rangierfahrten innerhalb eines Bahnhofs
- Kreis: Fahrplanmässiger Halt
- Quadrat: vom Fdl korrigierte Verspätung

## Werkzeuge

Eines oder zwei Liniensegmente werden durch Anklicken ausgewählt.
Die Auswahl wird durch Klicken auf den Hintergrund gelöscht.
Auf die gewählten Liniensegmente können folgende Aktionen aus der Werkzeugleiste angewendet werden.

- Abfahrtsverspätung einstellen
  - +/- 1 Minute
  - bei Abhängigkeit: zusätzliche Wartezeit
- Abhängigkeit bearbeiten
  - Ankunft/Kreuzung abwarten
  - Abfahrt/Überholung abwarten
  - zurücksetzen

Um eine Abhängigkeit zu setzen, müssen zwei Segmente ausgewählt werden.
Das erste (Auswahl, gelb) markiert den wartenden Zug, das zweite (Referenz, hellblau) den abzuwartenden Zug.


## Einstellungen

Die dargestellte Strecke wird auf der Einstellungsseite ausgewählt.
Es gibt zwei Arten, die Strecke auszuwählen:

### Vordefinierte Strecke aus der Anlagenkonfiguration

Strecken können in Modul Einstellungen manuell definiert und mit einem beliebigen Namen versehen werden.
Die Namen werden in der Auswahlbox aufgeführt.

Beim ersten Start eines Stellwerks, werden automatisch alle Strecken zwischen den verschiedenen Ein- und Ausfahrten hinzugefügt.
Diese entsprechen der automatischen Streckenwahl (s.u.) und sind möglicherweise nicht sinnvoll.
In diesen Fällen muss die Konfiguration manuell bearbeitet werden.

### Anfangs- und Endpunkt

Um diese Methode zu verwenden, darf keine vordefinierte Strecke ausgewählt sein.

Bei Auswahl eines Anfangs- und Endpunkts sucht das Programm den kürzesten Weg und schliesst die auf dem Weg liegenden Bahnhöfe ein.
Dabei können je nach Stellwerk auch unerwartete Ergebnisse auftreten.
In manchen Fällen hilft es, zusätzlich einen Via-Bahnhof auszuwählen.

Bei Stellwerken, in denen Züge über zwei verschiedene Anlageteile wie z.B. Neubau- und Altbaustrecken geleitet werden können,
sind in beiden Anlageteilen oft unsichtbare, gemeinsame Bahnsteige eingebaut.
Das Plugin hat keine Möglichkeit festzustellen, ob zwischen den Anlageteilen effektiv eine Gleisverbindung besteht.
In diesen Fällen versagt der Algorithmus.
Die Strecke muss manuell konfiguriert werden.

Die Teilstrecken Anfang-Via und Via-Ende können über die gleichen Bahnhöfe führen.
Das kann bei Kopfbahnhöfen sinnvoll sein.
Es ist jedoch möglich, dass Züge teilweise in der Darstellung fehlen.
In diesem Fall ist es besser, ein zweites Fenster mit der zweiten Strecke zu öffnen.


## Bemerkungen

Die Abstände auf der Wegachse werden nach Möglichkeit anhand der fahrplanmässigen Fahrzeiten zwischen den Bahnhöfen bestimmt.
Diese Bestimmung schlägt fehl, wenn keine an den Punkten haltenden Züge im Fahrplan enthalten sind, oder wenn der Fahrweg nicht eindeutig bestimmt werden kann.

Ausserdem kann die Bestimmung ungenau sein, wenn Züge im Fahrplan grosszüge oder stark richtungsabhängige Fahrzeitreserven haben.

Wenn mehrere Haltepunkte an einer Fahrstrasse liegen, hat das Plugin u. U. keine Möglichkeit, die Reihenfolge der Haltepunkte festzustellen.
