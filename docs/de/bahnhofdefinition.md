# Anschlüsse und Bahnhöfe

stsDispo verwendet ein hierarchisches Bahnhofmodell mit vier Ebenen.
Die Bezeichnungen sind an das Vorbild angelehnt, jedoch nicht deckungsgleich,
z.B. wird ein Haltepunkt in stsDispo als Bahnhof geführt.

![Bahnhofmodell](../img/bahnhofmodell.svg)

Die Pluginschnittstelle des Stellwerksim meldet nur Gleisnamen, aber keine Zuordnung zu Bahnhöfen, etc.
stsDispo versucht, die Zuordnung aus den Gleisnamen abzuleiten.
Dies funktioniert nicht in allen Stellwerken zuverlässig,
weshalb eine manuelle Bereinigung nötig ist.

## Bahnhofelemente

### Gleis (Gl) und Anschlussgleis (Agl)

Gleise und Anschlussgleise entsprechen genau denjenigen vom Simulator.
Die Namen können nicht geändert werden.

### Bahnsteig (Bs)

Ein Bahnsteig umfasst ein oder mehrere Gleise (Haltepunkte, Abschnitte, Sektoren).
Die Gruppierung dient in der Gleisbelegung dazu, eine Warnung anzuzeigen, 
wenn Züge denselben Bahnsteig belegen und in einer bestimmten Reihenfolge einfahren müssen.
Die automatische Gruppierung erfolgt anhand von Namensregeln.

### Bahnhofteil (Bft)

In einem Bahnhofteil werden normalerweise die Gleise zusammengefasst, 
auf die ein Zug im Funkmenü umgeleitet werden kann.
In stsDispo, dienen Bahnhofteile dazu, Gleise gruppenweise ein- oder auszublenden.
Der Name des Bahnhofteils kann beliebig gewählt werden.
Als automatische Vorgabe wird einer der Bahnsteignamen gewählt.
Bei Bahnhöfen, die aus einem einzigen Bft bestehen, wird empfohlen, für Bf und Bft den gleichen Namen zu verwenden.

### Bahnhof (Bf) und Anschlussstelle (Anst)

Bahnhöfe und Anschlussstellen werden an vielen Stellen in stsDispo verwendet,
z.B. bei der Streckendefinition oder der Berechnung von Fahrzeiten.
stsDispo leitet Bahnhöfe automatisch von Gleisnamen ab.
Wo dies nicht einwandfrei funktioniert, kann die Zuordnung manuell korrigiert werden.

## Bearbeitung

Das Bahnhofmodell wird mittels folgender Prozeduren bearbeitet.

### Zuordnen

Wenn Gleise (*Elemente*) zu einer falschen übergeordneten Gruppe gehören und die Zielgruppe bereits existiert:

1. Zuzuordnende Elemente in der Gleistabelle auswählen.
2. Zielgruppe aus der Liste im Kombifeld der entsprechenden Ebene auswählen.
3. Zugehörigen Knopf *Zuordnen* klicken.

Wenn die gewünschte Zielgruppe noch nicht existiert, zuerst gemäss Anleitung *Aufteilen* 
die alte Gruppe auflösen und ggf. bereinigen.

!!! example
    - Die automatische Konfiguration ordnet das Wendegleis `Wende A` dem Bahnhof `Wende` zu.
    Korrekt müsste es aber zum Bahnhof `A` gehören.
    - Um das zu korrigieren, das Gleis `Wende A` auswählen, aus der Bahnhofliste `A` auswählen und darunter *Zuordnen* klicken.
    - Das Gleis und sein Bahnhofteil `Wende A` werden in den Bahnhof `A` integriert.

### Aufteilen

Wenn Gruppen Elemente enthalten, die nicht zusammengehören:

1. Ein Gleis auswählen, das in eine neue Gruppe überführt werden soll.
2. Knopf *Aufteilen* der entsprechenden Gruppenebene klicken.
3. Die neue Gruppe erhält den Namen der direkten Untergruppe.
4. Neue Gruppen ggf. bereinigen oder umbenennen.

!!! example 
    - Haltepunkte in Österreich (z.B. `A H1`) sollen als eigene Bahnhöfe abgebildet werden,
    nachdem stsDispo sie fälschlich dem Bahnhof `A` zugeordnet hat (der Bahnhofteil `A H1` sei korrekt).
    - Zur Korrektur das Gleis `A H1` auswählen und *Bahnhof aufteilen* klicken.
    - Es wird ein neuer Bahnhof erstellt, der den Namen des Bahnhofteils des Gleises, also in diesem Fall `A H1`, übernimmt.

### Umbenennen

Alle Elemente ausser Gleisen können umbenannt werden.

1. Umzubenennendes Element in der Tabelle auswählen.
2. Neuen Namen im Kombifeld eintragen und den *Umbenennen*-Knopf klicken.
 
Der neue Namen muss auf der Ebene eindeutig sein, sonst wird er nicht angenommen.
