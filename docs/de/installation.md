# Installation

_STSkit_ läuft auf allen Plattformen, auf denen Python verfügbar ist (also u.a. Linux, Windows, MacOS). 
Es gibt zwei Wege, das Programm einzurichten und auszuführen:

1. [Quelltext](#quelltext). Funktioniert auf allen Systemen, auf denen Python verfügbar ist, erfordert aber (einfache) Operationen auf der Kommandozeile. Das GitHub-Repository ist immer auf dem neusten Stand.
2. [Ausführbare Programmdatei](#ausfuhrbare-programmdatei) für Windows, Ubuntu (latest LTS) und MacOS. Programmdateien werden nach bestem Wissen erstellt, es gibt keine Garantie, dass sie in allen Umgebungen funktionieren und frei von Fehlern oder schädlichem Code sind. Die Programmdateien werden automatisch erstellt und nicht getestet. Bei Problemen bitte einen Issue melden und bis zur Behebung eine ältere Version verwenden..

> STSdispo Version 2 verwendet ein neues Konfigurationsschema. Die alten Konfigurationsdaten werden automatisch migriert. Es wird empfohlen, ein Backup der alten Konfigurationsdateien zu erstellen.


## Quelltext

Die folgende Anleitung gilt für die aktuelle Version von STSdispo (Repository-Branch `master`).

STSkit benötigt Python 3.12 oder neuer.
Zur Installation wird uv verwendet.


### Schritt 1: uv installieren

Passenden uv Installer von https://docs.astral.sh/uv/ herunterladen und starten.
Andere Paketmanager (conda, pip) können verwendet werden, werden aber hier nicht beschrieben.


### Schritt 2: STSkit herunterladen

Quellcode als [zip-File](https://github.com/topological-state/stskit/archive/refs/heads/master.zip) aus dem GitHub-Repository herunterladen und in ein Zielverzeichnis deiner Wahl entpacken.

Anwender, die mit `git` vertraut sind, können alternativ das Repository klonen:

```
git clone https://github.com/topological-state/stskit.git
```

Die neuste Version wird danach jeweils durch folgenden Befehl heruntergeladen:

```
git pull
```


### Schritt 3: Stellwerksim starten

Stellwerksim mit einem beliebigen Stellwerk starten.


### Schritt 4: STSdispo starten

Terminal (bzw. Powershell auf Windows) öffnen und ins oben angelegte stskit-Verzeichnis wechseln. 
Das Verzeichnis muss die Datei `pyproject.toml` enthalten.

```
uv run stsdispo.py
```

uv lädt die notwendigen Python-Pakte herunter und startet das Programm.
Das Hauptfenster von STSdispo öffnet und verbindet sich mit dem laufenden Stellwerk.
Wenn beim Starten, Fehler auftreten, die Umgebung mit folgendem Befehl aktualisieren, und das Programm nochmals starten.

```
uv sync
```

Nach der ersten Installation sind zum Starten nur die Schritte 3-4 nötig.


## Ausführbare Programmdatei

### Schritt 1: Programmdatei herunterladen

Ausführbare Programmdateien für Windows (exe), Ubuntu (bin) und MacOS (app) werden soweit verfügbar unter [Releases](https://github.com/topological-state/stskit/releases/latest) im Abschnitt _Assets_ veröffentlicht.


### Schritt 2: Stellwerksim und STSdispo starten

1. Starte ein Stellwerk im Stellwerksim.
1. Starte das Programm `stsdispo.exe`.


## Kommandozeilen-Optionen

Ohne Angabe verbindet sich STSdispo mit dem laufenden Stellwerk auf dem gleichen Rechner. Wenn der Simulator auf einem anderen Rechner im gleichen Netzwerk oder auf einem anderen Port läuft, können die folgenden Optionen angegeben werden:

```
--host other-host --port 12345
```

Wenn Fehler auftreten, erstellt STSdispo eine Protokolldatei `stskit.log` im aktuellen Verzeichnis. Für mehr Details kann ein niedriger Log Level (WARNING, INFO or DEBUG) eingestellt werden. Ausserdem kann der Name der Protokolldatei angegeben werden:

```
--log-level DEBUG --log-file mylog.log
```
