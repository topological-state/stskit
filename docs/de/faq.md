# Fragen und Probleme (FAQ)

## Mysteriöse Abstürze und Fahrplanprobleme in Stellwerken mit Nummernwechseln

!!! info 
    Stskit benötigt das Wort "Gleis" in der Spalte "nach" des Fahrplans, um zu erkennen, dass ein Zug die Nummer wechselt und nicht ausfährt. 
    Der Grund dafür ist, dass es in einigen Stellwerken Gleise und Anschlüsse gibt, die den gleichen Namen tragen. 
    Siehe z.B. Issue [#132](https://github.com/topological-state/stskit/issues/132#issue-2245263699) oder [#130](https://github.com/topological-state/stskit/issues/130#issue-2078624002).

Stellt bitte sicher, dass in den Einstellungen des Stellwerksim-Kommunikators unter dem Reiter _Simulator_, das Feld _kein "Gleis" in "nach"_ **nicht markiert** ist!
