# Einstellungen

# Allgemeines

1. Wenn die automatische Konfiguration in einem Stellwerk nicht richtig funktioniert, kann sie hier korrigiert werden.  
2. Es wird empfohlen, zuerst die Anschlüsse und Bahnhöfe zu konfigurieren, erst dann die Strecken.
3. Änderungen an der Konfiguration werden möglicherweise erst nach einem Neustart des Plugins sichtbar.

## Anschlussstellen und Bahnhöfe

stsDispo verwendet ein hierarchiches Bahnhofmodell mit vier Ebenen:

![Gleismodell](docs/bahnhofgraph.png)

Die Pluginschnittstelle des Stellwerksim meldet nur Gleisnamen, aber keine Zuordnung zu Bahnhöfen, etc.
stsDispo versucht, die Zuordnung aus den Gleisnamen abzuleiten.
Dies funktioniert nicht in allen Stellwerken zuverlässig,
weshalb eine manuelle Bereinigung nötig ist.

### Bahnhofelemente

#### Gleis (Gl) und Anschlussgleis (Agl)

Gleise und Anschlussgleise entsprechen genau denjenigen vom Simulator.
Die Namen können nicht geändert werden.

#### Bahnsteig (Bs)

Ein Bahnsteig umfasst ein oder mehrere Gleise (Haltepunkte, Abschnitte, Sektoren).
Die Gruppierung dient in der Gleisbelegung dazu, eine Warnung anzuzeigen, 
wenn Züge denselben Bahnsteig belegen und in einer bestimmten Reihenfolge einfahren müssen.
Die automatische Gruppierung erfolgt anhand von Namensregeln.

#### Bahnhofteil (Bft)

In einem Bahnhofteil werden normalerweise die Gleise zusammengefasst, 
auf die ein Zug im Funkmenü umgeleitet werden kann.
In stsDispo, dienen Bahnhofteile dazu, Gleise gruppenweise ein- oder auszublenden.
Der Name des Bahnhofteils kann beliebig gewählt werden.
Als automatische Vorgabe wird einer der Bahnsteignamen gewählt. 

#### Bahnhof (Bf) und Anschlussstelle (Anst)

Bahnhöfe und Anschlussstellen werden an vielen Stellen in stsDispo verwendet,
z.B. bei der Streckendefinition oder der Berechnung von Fahrzeiten.
stsDispo leitet Bahnhöfe automatisch von Gleisnamen ab.
Wo dies nicht einwandfrei funktioniert, kann die Zuordnung manuell korrigiert werden.

### Bearbeitung

Das Bahnhofmodell wird mittels folgender Prozeduren bearbeitet.

#### Zuordnen

Wenn Gleise (*Elemente*) zu einer falschen übergeordneten Gruppe gehören und die Zielgruppe bereits existiert:

1. Zuzuordnenden Elemente in der Gleistabelle auswählen.
2. Zielgruppe aus der Liste im Kombifeld der entsprechenden Ebene auswählen.
3. Zugehörigen Knopf *Zuordnen* klicken.

Wenn die Zielgruppe noch nicht existiert, zuerst gemäss Anleitung *Aufteilen* 
die alte Gruppe auflösen und ggf. bereinigen.

#### Aufteilen

Wenn Gruppen Elemente enthalten, die nicht zusammengehören:

1. Ein Gleis der aufzuteilenden Gruppe auswählen.
2. Knopf *Aufteilen* der entsprechenden Gruppenebene klicken.
3. Neue Gruppen ggf. bereinigen oder umbenennen.

#### Umbenennen

Alle Elemente ausser Gleisen können umbenannt werden.

1. Umzubenennendes Element in der Tabelle auswählen.
2. Namen überschreiben und Eingabetaste drücken. 
   Alternativ den Namen im Kombifeld eintragen und den *Umbenennen*-Knopf klicken.
 
Der neue Namen muss auf der Ebene eindeutig sein, sonst wird er nicht angenommen.

## Strecken

Eine Strecke definiert eine Abfolge von Stationen (Anschlussstellen und Bahnhöfen),
die im Streckenfahrplan grafisch dargestellt werden kann.

Die konfigurierten Strecken können in der Listbox ausgewählt werden.
Mit dem Minusknopf wird die gewählte Strecke gelöscht, mit dem Plusknopf kann eine neue hinzugefügt werden.

Die aktuell gewählte Strecke wird in der Liste links dargestellt.
Die Liste rechts zeigt die von der Strecke nicht berührten Stationen.
Stationen können zwischen den Listen verschoben werden durch Klicken und Ziehen oder mittels der Links/Rechts-Knöpfe.
Stationen können innerhalb der Strecke angeordnet werden durck Klicken und Ziehen oder mittels der Hoch/Runter-Knöpfe.
Mit dem Ordnen-Knopf wird die Strecke automatisch geordnet.
Die automatische Ordnung kann jedoch fehlerhaft sein, insbesondere bei Haltepunkten.

## Zugschema

Das Zugschema für das laufende Stellwerk aus der Liste auswählen.
Die Bearbeitung der Zugschemata ist nur über Konfigurationsdateien möglich.


## Persistenz

Die hier gemachten Einstellungen werden beim Beenden des Programms in einer Konfigrurationsdatei im JSON-Format gespeichert.
Die Konfigurationsdatei befindet sich im Home-/User-Verzeichnis unter `.stskit`.
Der Dateiname entspricht der Anlagennummer im Stellwerksim.
Die Konfigurationsdateien können nach dem Umbau eines Stellwerks fehlerhaft werden.
Im Extremfall muss die entsprechende Konfigurationsdatei manuell gelöscht werden.
