# Konfiguration

Die Konfiguration eines Stellwerks legt die Zuordnung von Einfahrten/Ausfahrten, Bahnsteigen, Sektoren, Bahnhöfen und Strecken sowie einige weitere Einstellungen fest.
Die Konfiguration wird beim ersten Start eines Stellwerks (wenn vorhanden) aus einer im Programmpaket enthaltenen Vorlage übernommen oder sonst mit einer Reihe von Algorithmen automatisch erstellt. 
Die automatische Konfiguration reicht in den meisten Fällen für den Spielbetrieb aus.
In einigen Stellwerken, um kleinere Mängel auszubügeln, oder um eigene Präferenzen umzusetzen, muss die Konfiguration aber manuell nachbearbeitet werden. 

Ab Version 2 erfolgt die Bearbeitung im Programmmodul _Einstellungen_.
Die Konfigurationsdateien können theoretisch von Hand editiert werden.
Dies wird jedoch auf Grund der Komplexität nicht empfohlen.
Die weiteren Angaben auf dieser Seite sind für Experten gedacht.


## Name, Speicherort und Format

Die Konfigurationsdateien werden per Voreinstellung im Homeverzeichnis des Users erstellt.
Ein anderes Verzeichnis kann über eine Kommandozeilenoption gewählt werden.

Beispiele von Konfigurationsdateien sind im [config-Ordner](https://github.com/topological-state/stskit/tree/master/stskit/config) des stskit enthalten.
Da die Dokumentation auf dieser Seite möglicherweise nicht aktuell ist, empfiehlt es sich zusätzlich, die Vorlagen oder automatisch erzeugte Konfigurationen zu studieren.
Konfigurationsdateien zu weiteren Stellwerken können dem Autor zugeschickt oder via Pull-Request angeboten werden.

Der Name einer Konfigurationsdatei setzt sich aus der Stellwerk-ID und der Endung `json` zusammen.
Der Inhalt der Konfigurationsdateien ist im [JSON-Format](https://de.wikipedia.org/wiki/JavaScript_Object_Notation).
Bei JSON-Dateien auf Kommas, Klammern und (doppelte) Anführungszeichen achten!
Leerzeichen und Zeilenwechsel ausserhalb von Anführungszeichen sind rein kosmetisch. 
Umlaute im UTF-8 Encoding sind erlaubt.
Das STSdispo selber schreibt sie jedoch im `\u....` Format.
