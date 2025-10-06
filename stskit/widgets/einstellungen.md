# Einstellungen

# Allgemeines

- Wenn die automatische Konfiguration in einem Stellwerk nicht richtig funktioniert, kann sie hier korrigiert werden.  
- Zuerst die Anschlüsse und Bahnhöfe konfigurieren, danach die Strecken.
- Nach grösseren Änderungen oder vor einem Seitenwechsel *Anwenden* oder *OK* klicken.
- Es gibt kein Undo. *Zurücksetzen* stellt den zuletzt gespeicherten Zustand wieder her.

## Anschlussstellen und Bahnhöfe

stsDispo verwendet ein hierarchiches Bahnhofmodell mit vier Ebenen.
Die Bezeichnungen sind an das Vorbild angelehnt, jedoch nicht deckungsgleich,
z.B. wird ein Haltepunkt in stsDispo als Bahnhof geführt.

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

1. Zuzuordnende Elemente in der Gleistabelle auswählen.
2. Zielgruppe aus der Liste im Kombifeld der entsprechenden Ebene auswählen.
3. Zugehörigen Knopf *Zuordnen* klicken.

Wenn die gewünschte Zielgruppe noch nicht existiert, zuerst gemäss Anleitung *Aufteilen* 
die alte Gruppe auflösen und ggf. bereinigen.

> _Beispiel:_ 
> Die automatische Konfiguration ordnet das Wendegleis `Wende A` dem Bahnhof `Wende` zu.
> Korrekt müsste es aber zum Bahnhof `A` gehören.
> Um das zu korrigieren, das Gleis `Wende A` auswählen, aus der Bahnhofliste `A` auswählen und darunter *Zuordnen* klicken.
> Das Gleis und sein Bahnhofteil `Wende A` werden in den Bahnhof `A` integriert.

#### Aufteilen

Wenn Gruppen Elemente enthalten, die nicht zusammengehören:

1. Ein Gleis auswählen, das in eine neue Gruppe überführt werden soll.
2. Knopf *Aufteilen* der entsprechenden Gruppenebene klicken.
3. Die neue Gruppe erhält den Namen der direkten Untergruppe.
4. Neue Gruppen ggf. bereinigen oder umbenennen.

> _Beispiel:_ 
> Haltepunkte in Österreich (z.B. `A H1`) sollen als eigene Bahnhöfe abgebildet werden,
> nachdem stsDispo sie fälschlich dem Bahnhof `A` zugeordnet hat (der Bahnhofteil `A H1` sei korrekt).
> Zur Korrektur das Gleis `A H1` auswählen und *Bahnhof aufteilen* klicken.
> Es wird ein neuer Bahnhof erstellt, der den Namen des Bahnhofteils des Gleises, also in diesem Fall `A H1`, übernimmt.

#### Umbenennen

Alle Elemente ausser Gleisen können umbenannt werden.

1. Umzubenennendes Element in der Tabelle auswählen.
2. Neuen Namen im Kombifeld eintragen und den *Umbenennen*-Knopf klicken.
 
Der neue Namen muss auf der Ebene eindeutig sein, sonst wird er nicht angenommen.

## Strecken

Eine Strecke definiert eine Abfolge von Stationen (Anschlussstellen und Bahnhöfen),
die im Streckenfahrplan grafisch dargestellt werden kann.

Die konfigurierten Strecken können in der Listbox ausgewählt werden.
Die aktuell gewählte Strecke wird in der Liste links unten dargestellt.

Kursiv gesetzte Namen bezeichnen automatisch erstellte Strecken.
Automatische Strecken werden bei Stellwerkupdates angepasst.
Der Algorithmus kann jedoch in gewissen Stellwerken unzuverlässig sein.
Mit den Knöpfen rechts können Strecken gelöscht, erstellt oder umbenannt werden.

Mit dem Auswahlfeld kann eine Hauptstrecke ausgewählt werden.
Diese wird beim Öffnen des Streckenfahrplans voreingestellt.
Es empfiehlt sich also, hier die am Häufigsten benutzte Strecke zu markieren.

Die Boxen unten zeigen zwei Listen von Stationen.
Die linke Liste zeigt die aktuell bearbeitete Strecke,
die rechte Liste enthält die von der Strecke unberührten Stationen.

Stationen können zwischen den Listen verschoben werden durch Klicken und Ziehen oder mittels der Links/Rechts-Knöpfe.
Stationen können innerhalb der Strecke angeordnet werden durck Klicken und Ziehen oder mittels der Hoch/Runter-Knöpfe.

Mit dem Ordnen-Knopf wird die Strecke automatisch geordnet,
der Interpolieren-Knopf fügt automatisch Stationen zwischen der ersten und letzten der Liste hinzu.
Die bei diesen Funktionen benutzten Algorithmen können bei gewissen Stellwerken unzuverlässig sein.
In diesem Fall muss die Strecke manuell konfiguriert werden.
Manchmal hilft es auch, das Fenster zu schliessen und neu zu Öffnen, um den Bahnhofplan neu zu laden.

_Empfehlungen:_
- Es empfiehlt sich, möglichst wenige Strecken zu definieren.
  Viele der automatisch erstellten Strecken sind zu kurz und können gelöscht werden.
- Da der Streckenfahrplan von links nach rechts dargestellt wird,
  sollte der Anfangspunkt eher links oben im Stellwerk liegen, der Endpunkt relativ dazu gesehen rechts unten.
- Als Start- und Endpunkt können sowohl Anschlussstellen wie Bahnhöfe verwendet werden.
  Anschlüsse können innerhalb der Strecke vorkommen, 
  je nach Konfiguration kann dies jedoch die Darstellung des Streckenfahrplans beeinträchtigen.
- Etwas Experimentieren kann nötig sein.


## Zugschema

Das Zugschema für das laufende Stellwerk aus der Liste auswählen.
Die Bearbeitung der Zugschemata ist nur über Konfigurationsdateien möglich.


## Persistenz

Die hier gemachten Einstellungen werden beim Beenden des Programms in einer Konfigurationsdatei im JSON-Format gespeichert.
Die Konfigurationsdatei befindet sich im Home-/User-Verzeichnis unter `.stskit`.
Der Dateiname entspricht der Anlagennummer im Stellwerksim.
Die Konfigurationsdateien können nach dem Umbau eines Stellwerks fehlerhaft werden.
Im Extremfall muss die entsprechende Konfigurationsdatei manuell gelöscht werden.
