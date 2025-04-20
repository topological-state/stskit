# Einstellungen

Die Pluginschnittstelle des Stellwerksim meldet nur Gleisnamen, keine Bahnhöfe.
stsDispo versucht, Bahnhofsnamen aus den Gleisnamen abzuleiten.
Das funktioniert jedoch nicht in allen Fällen, 
weil das Schema von Gleisnamen nicht vorgegeben ist
und von Stellwerk zu Stellwerk anders gehandhabt wird.
In diesen Fällen, muss das Gleismodell, insbesondere die Bahnhofszuordnung, manuell bearbeitet werden.

Die hier gemachten Einstellungen werden beim Beenden des Programms in einer Konfigrurationsdatei im JSON-Format gespeichert.
Die Konfigurationsdatei befindet sich im Home-/User-Verzeichnis unter `.stskit`.
Der Dateiname entspricht der Anlagennummer im Stellwerksim.
Die Konfigurationsdateien können nach dem Umbau eines Stellwerks fehlerhaft werden.
Im Extremfall muss die entsprechende Konfigurationsdatei manuell gelöscht werden.

## Anschlussstellen und Bahnhöfe

stsDispo verwendet folgendes Gleismodell:

![Gleismodell](docs/bahnhofgraph.png)

### Bahnhofelemente

#### Gleis (Gl) und Anschlussgleis (Agl)

Gleise und Anschlussgleise entsprechen genau denjenigen vom Simulator.
Die Namen können nicht geändert werden.

#### Bahnsteig (Bs)

Ein Bahnsteig umfasst ein oder mehrere Gleise (Haltepunkte, Abschnitte, Sektoren).
Die Gruppierung dient in der Gleisbelegung dazu, eine Warnung anzuzeigen, 
wenn Züge denselben Bahnsteig belegen und in einer bestimmten Reihenfolge einfahren müssen.

Die automatische Gruppierung erfolgt anhand von Namensregeln.
Sie muss bei einigen Stellwerken korrigiert werden.

#### Bahnhofteil (Bft)

In einem Bahnhofteil werden die Gleise zusammengefasst, 
auf die ein Zug im Funkmenü umgeleitet werden kann.

Der Name des Bahnhofteils erscheint in den Diagrammen nicht und ist daher unwichtig.
Als Vorgabe wird einer der Bahnsteignamen gewählt. 

#### Bahnhof (Bf) und Anschlussstelle (Anst)

Bahnhöfe und Anschlussstellen werden an vielen Stellen in stsDispo verwendet
und bilden die Eckpunkte des Fahrzeitenmodells.

stsDispo leitet Bahnhöfe automatisch von Gleisnamen ab.
Wo dies nicht einwandfrei funktioniert, muss der Fdl das Modell korrigieren.

### Bearbeitung

Zur Bearbeitung des Gleismodells dienen die folgenden drei Prozeduren.

#### Zuordnen

Wenn Gleise, Bahnhofteile oder Anschlussgleise zur falschen Gruppe gehören und die Zielgruppe bereits existiert:

1. Gleise der zuzuordnenden Elemente in der Tabelle auswählen.
2. Liste im entsprechenden Kombifeld aufklappen und Zielgruppe auswählen.
3. Zugehörigen Knopf *Zuordnen* klicken.

Wenn die Zielgruppe noch nicht existiert, zuerst gemäss Anleitung *Aufteilen* 
die alte Gruppe auflösen und ggf. die neuen Gruppen umbenennen.

#### Aufteilen

Wenn Bahnsteige, Bahnhöfe und Anschlussstellen Elemente enthalten, die nicht zusammengehören:

1. Ein Gleis der aufzuteilenden Gruppe auswählen.
2. *Neuer Bahnsteig*, *Neuer Bahnhofteil* bzw. *Neue Anschlusstelle* klicken.
3. Neue Gruppen ggf. umbenennen.

#### Umbenennen

Bahnsteige, Bahnhofteile, Bahnhöfe und Anschlussstellen können umbenannt werden:

1. Ein Gleis das zur umzubenennenden Gruppe gehört auswählen.
2. Neuen Namen im Editierfeld eintragen.
3. Umbenennen-Knopf drücken.

## Strecken

...

## Zugschema

Das Zugschema für das laufende Stellwerk aus der Liste auswählen.
Die Bearbeitung der Zugschemata ist im Moment nur über Konfigurationsdateien möglich.
