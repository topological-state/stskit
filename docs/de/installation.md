# Installation

_STSkit_ läuft auf allen Plattformen, auf denen Python 3.12 verfügbar ist (also u.a. Linux, Windows, MacOS).
Es gibt zwei Wege, das Programm einzurichten und auszuführen:

1. [Quelltext](#quelltext). 
   Funktioniert auf allen Systemen, auf denen Python verfügbar ist, erfordert aber die Installation von weiteren Programmen und Kenntnis der Kommandozeile. 
   Neuentwicklungen sind schneller verfügbar.
   Es gibt keine Gewähr, dass die Programme frei von Fehlern oder schädlichem Code sind.
2. [Ausführbare Programmdatei](#ausfuhrbare-programmdatei) für Windows, Ubuntu (neuste LTS) und MacOS. 
   Die Programmdateien werden automatisch erstellt und nicht getestet. 
   Es gibt keine Gewähr, dass die Programme in allen Umgebungen funktionieren und frei von Fehlern oder schädlichem Code sind. 
   Bei Problemen bitte einen [Issue](https://github.com/topological-state/stskit/issues) melden und bis zur Behebung eine ältere Version verwenden.

!!! warning

    STSdispo Version 2 verwendet ein neues Konfigurationsschema. 
    Die alten Konfigurationsdaten werden automatisch migriert und können nachher nicht mehr mit Version 1 verwendet werden.
    Es wird empfohlen, ein Backup der alten Konfigurationsdateien zu erstellen.


## Quelltext

Die folgende Anleitung gilt für die aktuelle Version von STSdispo (Repository-Branch `master`).
STSkit benötigt Python 3.12 oder neuer.
Zur Installation wird der [uv]-Paketmanager benötigt.

  [git]: https://git-scm.com/
  [uv]: https://docs.astral.sh/uv/

### Schritt 1: uv installieren

Passenden [uv-Installer][uv] herunterladen und starten.
Andere Paketmanager (conda, pip) können verwendet werden, werden aber hier nicht beschrieben.

=== "MacOs und Linux"

    ``` sh
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    ``` ps
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

Dieser Schritt ist nur einmal nötig.

### Schritt 2: STSkit herunterladen

Quellcode als [zip-File](https://github.com/topological-state/stskit/archive/refs/heads/master.zip) aus dem GitHub-Repository herunterladen und in ein beliebiges Zielverzeichnis entpacken.

Anwender, die mit [git] vertraut sind, können alternativ das Repository klonen:

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

uv lädt die notwendigen Python-Pakete herunter und startet das Programm.
Das Hauptfenster von STSdispo öffnet und verbindet sich mit dem laufenden Stellwerk.
Nach dem Verlassen des Stellwerks, das Hauptfenster von STSdispo schliessen.

Wenn beim Starten, Fehler auftreten, die auf eine inkompatible Python-Version hindeuten, 
die Umgebung mit folgendem Befehl aktualisieren und das Programm nochmals starten.

```
uv sync --reinstall
```


## Ausführbare Programmdatei

### Schritt 1: Programmdatei herunterladen

Ausführbare Programmdateien für Windows (exe), Ubuntu (bin) und MacOS (app) werden soweit verfügbar unter [Releases](https://github.com/topological-state/stskit/releases/latest) im Abschnitt _Assets_ veröffentlicht.
Beachte bitte die Release Notes Anderungen der Bedienung oder Inkompatibilitäten zu früheren Versionen.

### Schritt 2: Stellwerksim und STSdispo starten

1. Gewünschtes Stellwerk im Stellwerksim starten.
2. Programm `stsdispo.exe` (Windows) starten.
   STSdispo verbindet sich mit dem laufenden Stellwerk auf dem gleichen Rechner.
3. Nach dem Beenden des Stellwerks, das Hauptfenster von STSdispo schliessen.


## Kommandozeilen-Optionen

Ohne Angabe von Optionen verbindet sich STSdispo mit dem laufenden Stellwerk auf dem gleichen Rechner. 
Wenn der Simulator auf einem anderen Rechner im gleichen Netzwerk oder auf einem anderen Port läuft, können die folgenden Optionen angegeben werden:

```
uv run stsdispo.py --host other-host --port 12345
```

Wenn Fehler auftreten, erstellt STSdispo eine Protokolldatei `stskit.log` im aktuellen Verzeichnis. 
Für mehr Details kann ein niedriger Loglevel (WARNING, INFO or DEBUG) eingestellt werden. 
Ausserdem kann der Name der Protokolldatei angegeben werden:

```
uv run stsdispo.py --log-level DEBUG --log-file mylog.log
```

Eine vollständige Liste von Optionen gibt der folgende Befehl aus:

```
uv run stsdispo.py --help
```
