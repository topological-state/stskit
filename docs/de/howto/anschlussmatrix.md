# Anschlussmatrix

Die Anschlussmatrix zeigt den Status der Anschlüsse.
Anschlüsse sind Relationen zwischen Ankünften und Abfahrten in einem Bahnhof, 
die fahrplanmässig innerhalb eines bestimmten Zeitfensters liegen.
Die Zeit zwischen Ankunft und Abfahrt muss länger als die benötigte Umsteigezeit und kürzer als die maximale Anschlusszeit sein.

![stskit-screen-anschlussmatrix](https://user-images.githubusercontent.com/51272421/210151697-f7038fe0-3402-422a-a0b4-6926c2c19a01.png)

## Markierungen

- blau: Anschluss, voraussichtlich erfüllt
- grün: Anschluss erfüllt, Umsteigezeit erreicht, Zug kann abfahren
- rot: gebrochener Anschluss, Umsteigezeit reicht nicht
- rosa: Kupplung, Zug muss auf zweiten Zugteil warten
- orange: Fdl-Entscheid: Anschlusszug wartet
- violet: Fdl-Entscheid: Anschluss wird gebrochen
- grau: gleicher Zug

Die Zahl in den Feldern gibt die Verspätung an, die der Zug haben wird, wenn er den Anschluss abwartet.

Flügelungen sind an zwei grauen Feldern in einer Spalte erkennbar.

## Werkzeuge

Einer oder mehrere Anschlüsse werden durch Klicken auf die farbigen Felder oder die Zugbeschriftung ausgewählt.
Klicken auf den Hintergrund löscht die Auswahl.
Auf ausgewählte Anschlüsse können folgende Aktionen der Werkzeugleiste angewendet werden.

- Zug verbergen
- Verborgene züge wieder anzeigen
- Ankunft abwarten
- Abfahrt abwarten
- Anschluss auflösen
- Anschlussstatus zurücksetzen
- Wartezeit erhöhen/erniedrigen

Alle Aktionen haben ein Tastaturkürzel.
Das Kürzel wird im Tooltip angezeigt.

## Einstellungen

Auf der Einstellungsseite einstellbar sind:

- Umsteigezeit
- Anschlusszeit
- Zusammensetzung der Zugbeschriftung (Gleis, Zugnummer, Zeit, Verspätung)

## Bemerkungen

Anschlüsse sind allein durch die Fahrplanzeiten gegeben.
Die Matrix kann Güterzüge oder S-Bahnzüge oder in entgegengesetzter Richtung verkehrende Züge nicht automatisch herausfiltern.
Güterzüge oder verspätete Züge können durch die Aktion _Zug verbergen_ aus der Matrix entfernt werden.
