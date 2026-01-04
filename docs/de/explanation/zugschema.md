Das Zugschema bestimmt die Kategorisierung und die Farbgebung der Züge.
Für jedes Stellwerk kann ein eigenes Schema ausgewählt werden.
In der Regel benutzen jedoch alle Stellwerke einer Region dasselbe Schema.
Der Benutzer kann die vorgegebenen Schemas verwenden oder eigene erstellen.

Das Zugschema kann im Hauptmenü unter Einstellungen / Zugschema ausgewählt werden.
Das Fenster zeigt ausserdem das Schema an.
Die Einträge können hier nicht bearbeitet werden.

Die vorgegebenen Zugschemas teilen die Zuggattungen in 10 Kategorien ein, die mit unterschiedlichen Farben markiert werden.
Bei der Erstellung der Schemas wurde so gut wie möglich auf eine einheitliche Farbgebung in allen Regionen geachtet,
so dass z.B. ein Fernverkehrszug in allen Regionen orange dargestellt wird.
Bei der Farbzuteilung wurde darauf geachtet, dass Personenzüge gut von Güterzügen unterschieden werden können,
und dass Hochgeschwindigkeitszüge sowie Sonderprofilzüge speziell markiert werden.
Die folgende Tabelle erläutert das Farbkonzept.

| Kürzel | Beschreibung | Farbe |
|:---:|:---|:---:|
| X | Hochgeschwindigkeitszug, internationaler Schnellzug | rot |
| F | Fernverkehrszug | orange |
| N | Nahverkehr | olivgrün |
| S | S-Bahn | braun |
| G | Güterzug | blau |
| E | Schneller Güterzug, Post | hellblau |
| K | Kombiverkehr, Container, RoLa | violett |
| D | Dienstzug, Leerfahrt, Lokzug | grün |
| O | Sonderzug, Bauzug, Sonderprofilzug | rosa |
| R | Rangierverkehr | grau |

Die Kategorien werden entweder nach Gattungsname (in den meisten Regionen) und/oder nach Zugnummer (Schweiz, Italien, Grossbritannien) zugeteilt. Die Abbildungen unten zeigen als Beispiele die Zugschemas von Frankreich und der Schweiz.

![zugschema frankreich](https://github.com/topological-state/stskit/assets/51272421/e0d61c69-16e8-4855-bf7e-b3d75e71e0a6)
![zugschema schweiz](https://github.com/topological-state/stskit/assets/51272421/08cf54b6-e809-4703-8656-eb7710524f9e)

Die Vorlagen befinden sich im Ordner `stskit/config`.
Ihr Dateiname lautet `zugschema.name.json`, wobei der Name beliebig sein kann.
Der im Einstellungsfenster angezeigte Name steht in der Datei im `titel`-Attribut.

Benutzerspezifische Zugschema-Dateien sollte im persönlichen .stskit-Ordner abgelegt werden, siehe Konfiguration.
