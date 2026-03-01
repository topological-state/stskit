
# STSkit / STSdispo

[Stellwerksim](https://www.stellwerksim.de) ist ein kollaboratives, Online-Stellwerksimulatorspiel.
Das _STSkit_-Paket enthält verschiedene Plugins zu [Stellwerksim](https://www.stellwerksim.de), die dich beim Spiel unterstützen.
Das Hauptprogramm _STSdispo_ bietet eine Reihe von grafischen Werkzeugen wie Bildfahrplan, Gleisbelegung und Anschlussmatrix.
Es liest die Live-Daten des laufenden Spiels aus, stellt sie grafisch dar, und unterstützt dich bei der Disposition.

_STSkit_ enthält eine Implementierung der Stellwerksim Plugin-Schnittstelle in Python, die du auch in eigenen Projekten verwenden kannst.


## Hauptmerkmale

- Grafische und tabellarische Fahrpläne
    - Automatische Verspätungsprognose entlang der Zugketten mit Berücksichtigung der verschiedenen Betriebsvorgänge.
    - Korrekturmöglichkeiten und Erfassung von Abhängigkeiten (Anschlüsse, Kreuzungen, Überholungen)
- Gleisbelegungsplan
    - Warnung vor Gleis- und Sektorkonflikten
    - Hervorhebung von Kupplungsvorgängen
- Einfahrts- und Ausfahrtstabellen
    - Abschätzung der effektiven Ein- und Ausfahrtszeiten
- Anschlussmatrix
- Rangierplan
- Ereignisticker
- Asynchrone, objektorientierte Python-Schnittstelle für Stellwerksim-Plugins


Der Fokus des Projekts liegt auf der Auswertung von Fahrplandaten und der aktuellen Betriebslage, um eine möglichst reibungslose Disposition der Züge zu ermöglichen.
Verspätungen werden entlang der Zugketten hochgerechnet und können vom Fdl korrigiert werden.
