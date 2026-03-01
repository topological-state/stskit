# Zugfahrplan

Im Zugfahrplan können die Details der Züge eingesehen werden.

Das Fenster zeigt auch die von stskit verwalteten Verspätungsparameter an,
was unter anderem für die Problemlösung bei Fehlfunktionen hilfreich sein kann.

![stskit-screen-tabellenfahrplan](https://user-images.githubusercontent.com/51272421/210151709-b9c46270-db98-4583-86d0-612a24fe2009.png)

Auf der linken Seite werden alle (dem Plugin bekannten) Züge aufgelistet.
Die Zugliste kann durch Klicken auf einen Spaltentitel sortiert werden.
Durch Klicken auf einen Zug wird sein Fahrplan auf der rechten Seite eingeblendet.
Falls vorhanden, wird zudem der Fahrplan des Folgezugs eingeblendet.

## Zugliste

- zid: Die Zeilennummer ist die Zugsnummer, die vom Simulator intern verwendet wird und für den Benutzer normalerweise nicht sichtbar ist.
- Status
  - E: noch nicht eingefahren
  - S: im Stellwerk sichtbar
  - A: ausgefahren
- Einfahrt: von stskit prognostizierte Einfahrtszeit (s. [Modul Ein-/Ausfahrten](howto/ein-ausfahrten.md))
- Zug, Von, Nach, Gleis, Verspätung: entsprechen den Informationen im Simulator


## Zugfahrplan

- Gleis, An, Ab: entsprechen den Information im Simulator
- VAn, VAb: von stskit geschätzte Ankunfts- und Abfahrtsverspätung
- Flags: vom Simulator übermittelte Flagzeile (s. Erbauerhandbuch)
- Folgezug: Zugnummer des Folgezugs bei Ersatz, Kupplung oder Flügelung
- Abhängigkeiten: s.u.

Bei sichtbaren Zügen wird das aktuelle Fahrplanziel hellblau hervorgehoben.


## Abhängigkeiten

Diese Spalte zeigt, nach welchen Abhängigkeiten die Verspätung berechnet wird.
Jedem Fahrplanziel ist eine automatische Abhängigkeit zugeordnet, die von stskit intern verwaltet wird.
Ausserdem kann der Fdl weitere Abhängigkeiten anfügen.

### Automatische Abhängigkeiten

- Einfahrt: Verfolgt die Verspätung noch nicht eingefahrener Züge
- Plan: Fahrplanmässiger Halt, wenn möglich Verspätung aufholen
- Signal: übernimmt die Verspätung bei einem ausserordentlichen Halt
- Ersatz: Verspätungsberechnung bei Ersatz/Nummernwechsel
- Kupplung: Verspätungsberechnung bei Kupplung
- Flügelung: Verspätungsberechnung bei Flügelung
- Flag: Verspätung wird durch Flag (Ersatz/Kupplung/Flügelung) bestimmt

### Vom Fdl verwaltete Abhängigkeiten

- Abfahrt: Abfahrt eines anderen Zuges abwarten
- Ankunft: Ankunft eines anderen Zuges abwarten
- Fest: Der Fdl hat eine feste Verspätung angegeben
- Nicht warten: Anderen Zug nicht abwarten

## Werkzeuge

In diesem Fenster sind keine Werkzeuge verfügbar.
Abhängigkeiten werden in den anderen Modulen bearbeitet.
