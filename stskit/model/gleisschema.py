"""
Gleischema: Übersetzung von Gleisnamen in Bahnhofnamen

Das Gleisschema ordnet den Gleisen einen Bahnsteig- und einen Bahnhofnamen zu.
Anschlussgleisen ordnet es eine Anschlussstelle zu.
Es ist mittels Konfigurationsdateien einstellbar.

"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, Generator, Iterable, List, Mapping, Set, Tuple

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Uebersetzung von Regionen in Schema-Regionen (Regionen, die das gleiche Schema verwenden).
# Das erste Wort des Regionsnamens ist ausschlaggebend.
REGIONEN_SCHEMA = {
    "Belgien": "Benelux",
    "Bern": "Schweiz",
    "Grand": "Frankreich",
    "Großbritannien": "Grossbritannien",
    "Hauts-de-France": "Frankreich",
    "Île-de-France": "Frankreich",
    "Italien": "Italien",
    "Luxemburg": "Benelux",
    "Merxferri": "Deutschland",
    "Niederlande": "Benelux",
    "Ostschweiz": "Schweiz",
    "Polen": "Polen",
    "Sverige": "Schweden",
    "Tessin": "Schweiz",
    "Tschechien": "Tschechien",
    "Westschweiz": "Schweiz",
    "Zentralschweiz": "Schweiz",
    "Zürich": "Schweiz"
    }


# \d digit
# \s whitespace
# \w word/alphanumeric including underscore

ALPHA_PREFIX_PATTERN = re.compile(r'[^\d\W]*')
NON_DIGIT_PREFIX_PATTERN = re.compile(r'\D*')
ALPHANUMERISCHES_GLEIS_PATTERN = re.compile(r'([^\d\W]*)\s*(\w*)')
ENTHAELT_ZIFFER_REGEX = re.compile(r'\D*\d+\D*')
BAHNSTEIG_VON_SEKTOR_REGEX = re.compile(r'\D*\d+')
HALTESTELLE_OESTERREICH_REGEX = re.compile(r'\D+\s[AHKSU]\d\D?')

# extrahiert die gleisnummer, wenn sie numerisch ist
# beispiele Aa5a, Aa 5a, AA 5a G
GLEISNUMMER_REGEX = re.compile(r'\D*(\d+\w*)\D*')

# teilt den gleisnamen an der ersten numerischen sequenz in drei gruppen auf: präfix, nummer, suffix
GLEISNAME_REGEXP = re.compile(r"(\D*)(\d*)(\D*)")

EINZEL_ANSCHLUESSE = ['Anschluss', 'Feld', 'Gruppe', 'Gleis', 'Gr.', 'Anschl.', 'Gl.', 'Industrie', 'Depot',
                      'Abstellung']


def common_prefix(lst: Iterable) -> Generator[str, None, None]:
    for s in zip(*lst):
        if len(set(s)) == 1:
            yield s[0]
        else:
            return


def gemeinsamer_name(g: Iterable) -> str:
    return ''.join(common_prefix(g)).strip()


def alpha_prefix(name: str) -> str:
    """
    Alphabetischen Anfang eines Namens extrahieren.

    Anfang des Namens bis zum ersten nicht-alphabetischen Zeichen (Ziffer, Leerzeichen, Sonderzeichen).
    Umlaute etc. werden als alphabetisch betrachtet.
    Leerer String, wenn keine alphabetischen Zeichen gefunden wurden.

    Args:
        name: Z.B. Gleisname.

    Returns:
        Resultat.
    """
    return re.match(ALPHA_PREFIX_PATTERN, name).group(0)


class Gleisschema:
    REGISTRY = {}

    def __init__(self):
        self.stellwerk: str = 'Hbf'
        self.region: str = 'default'
        self.schema: str = 'default'

    @staticmethod
    def regionsschema(stellwerk: str,
                      region: str,
                      ) -> Gleisschema:
        """
        Gleisschema anhand Region ermitteln und instanziieren.

        Der Name des Schemas wird zunächst anhand des ersten Wortes der Region ermittelt (REGIONEN_SCHEMA).
        Anschliessend wird das in Gleisschema.REGISTRY registrierte Schema instanziiert.
        Wenn die Region nicht in der REGIONEN_SCHEMA-Liste enthalten ist, wird das Standardgleisschema verwendet.

        Args:
            stellwerk: Name des Stellwerks
            region: z.b. 'Berlin Ostbahnhof'

        Returns:
            Gleisschema
        """

        try:
            schema = REGIONEN_SCHEMA[region.split(maxsplit=1)[0]].lower()
        except (IndexError, KeyError):
            schema = 'default'
        cls = Gleisschema.REGISTRY.get(schema, Gleisschema)
        obj = cls()
        obj.stellwerk = stellwerk
        obj.region = region
        return obj

    def bahnsteigname(self, gleis: str) -> str:
        """
        Bahnsteignamen aus Gleisnamen ableiten.

        Der Bahnsteigname ist der Gruppenname von Gleissektoren.
        Diese Funktion liefert alle Zeichen aus dem Gleisnamen bis zur letzten Ziffer.
        Auf die Ziffer folgende nicht-numerische Zeichen werden ignoriert.

        Bahnsteigname bezieht sich auf die Verwendung im Bahnhofgraphen
        und nicht auf den Bahnsteig in der Plugin-Schnittstelle.

        Args:
            gleis: Gleisname (Bahnsteigname in der Plugin-Schnittstelle)

        Returns:
            Bahnsteigname
        """
        mo = re.match(BAHNSTEIG_VON_SEKTOR_REGEX, gleis)
        if mo:
            bs = mo[0]
        else:
            bs = gleis
        return bs

    def bahnhofname(self, gleis: str) -> str:
        """
        Bahnhofnamen aus Gleisnamen ableiten.

        Es gibt kein einheitliches Schema für Gleisnamen, aus dem sich der Bahnhofsname ableiten lässt.
        Diese Funktion implementiert daher eine Heuristik, die in den meisten Fällen einen brauchbaren Vorschlag liefert.
        Sie kann aber nicht alle Fälle korrekt verarbeiten, weil der Gleisname nicht genug Information enthält.
        Diese Fälle müssen manuell korrigiert werden.

        Die Funktion testet folgende Regeln und gibt das Resultat der ersten passenden Regel aus:

        1. Wenn der Gleisname mit einer Ziffer beginnt: "Hbf".
        2. Wenn der Gleisname keine Ziffer enthält, den ganzen Gleisnamen.
        2. Rein alphabetischer Teil bis zum ersten Leerzeichen, auf das ein Wort folgt, das eine Ziffer enthält.
        3. Alphabetischer Teil bis zur ersten Ziffer.

        Beispiele:

        ```
        FSP503 -> FSP
        NAH423b -> NAH
        6 -> _Stellwerksname_
        10C-D -> _Stellwerksname_
        BSGB D73 -> BSGB
        ZUE 12 -> ZUE
        BR 1b -> BR
        Lie W10 -> Lie
        Muntelier-L. -> Muntelier-L.
        VU3-5 -> VU
        Isola della Scala 3G -> Isola della Scala
        ```

        Beachte, dass Bahnhofs- und Gleisbezeichnungen Leerzeichen und Sonderzeichen enthalten können.
        In den folgenden Fällen (nicht abschliessend),
        liefert die Funktion nicht das gewünschte Ergebnis (in Klammern).

        ```
        Brennero: R3 -> R (Hbf), N -> N (Hbf)
        Drautal: Lie A1 -> Lie (Lie A1), Ma Wende R -> Ma Wende R (Ma)
        ```

        Args:
            gleis: Gleis- bzw. Bahnsteigname

        Returns:
            Bahnhofname
        """

        teile = gleis.split()
        alpha_teile = []

        if HALTESTELLE_OESTERREICH_REGEX.match(gleis):
            return gleis

        for teil in teile:
            if ENTHAELT_ZIFFER_REGEX.search(teil):
                break
            elif teil.lower() in {"wende", "lang", "kurz"}:
                break
            else:
                alpha_teile.append(teil)
        name = " ".join(alpha_teile)

        if not name:
            name = NON_DIGIT_PREFIX_PATTERN.match(teile[0].strip()).group(0)

        if name:
            return name
        else:
            return self.stellwerk

    def gleisname_kurz(self, gleis: str) -> str:
        """
        Gleisnamen abkürzen.

        Die Abkürzung wird in Grafiken verwendet, wo eine möglichst kurze Beschriftung verwendet werden soll.
        Das Resultat dieser Funktion ist nicht eindeutig und
        kann in der Programmlogik nicht als Gleisidentifikation verwendet werden.


        Args:
            gleis: Gleis- bzw. Bahnsteigname

        Returns:
            Gleisnummer (String), extrahiert aus Gleisnamen.
                Wenn der Gleisname eine Ziffer enthält, ist das der Substring ab der Ziffer bis zum Ende oder nächsten Leerzeichen,
                wenn der Gleisname keine Ziffer aber Leerzeichen enthält, der zweite Teilstring geliefert,
                ansonsten der unveränderte Gleisname.
        """

        mo = GLEISNUMMER_REGEX.match(gleis)
        if mo:
            return mo.group(1)
        else:
            teile = gleis.split()
            if len(teile) > 1:
                return teile[1]
            else:
                return teile[0]

    def ist_einzel_anschluss(self, gleis: str) -> bool:
        """
        Prüft anhand von Schlüsselwörtern, ob das Gleis ein einfacher Anschluss ist.

        Zeigt True, wenn eine Zeichenfolge aus EINZEL_ANSCHLUESSE im Gleisnamen vorkommt.

        Args:
            gleis: Name des Anschlussgleises.

        Returns:
            True, wenn eine Zeichenfolge aus EINZEL_ANSCHLUESSE im Gleisnamen vorkommt.
        """
        for ea in EINZEL_ANSCHLUESSE:
            if gleis.find(ea) >= 0:
                return True

        return False

    def anschlussname(self, gleis: str) -> str:
        """
        Anschlussname aus Gleisnamen ableiten.

        Es wird angenommen, dass der Bahnhofname aus den alphabetischen Zeichen am Anfang des Gleisnamens besteht.

        Wenn der Gleisname keine alphabetischen Zeichen enthält
        oder eine Zeichenfolge aus EINZEL_ANSCHLUESSE im Gleisnamen vorkommt, wird der Gleisname unverändert zurückgegeben.

        Args:
            gleis: Gleisname.

        Returns:
            Anschlussname.
        """

        if self.ist_einzel_anschluss(gleis):
            return gleis
        else:
            anschluss = NON_DIGIT_PREFIX_PATTERN.match(gleis).group(0).strip()
            if anschluss:
                return anschluss
            else:
                return gleis

    def gleisname_sortkey(self, gleis: str) -> Tuple[str, int, str]:
        """
        Gleisname in Sortierschlüssel umwandeln.

        Annahme: Gleisname setzt sich aus Präfix, Nummer und Suffix zusammen.
        Präfix und Suffix bestehen aus Buchstaben und Leerzeichen oder fehlen ganz.
        Präfix und Suffix können durch Leerzeichen von der Nummer abgetrennt sein, müssen aber nicht.

        Args:
            gleis: Gleisname, wie er im Fahrplan der Züge steht.

        Returns:
            Tupel (Präfix, Nummer, Suffix). Leerzeichen entfernt.
        """

        mo = re.match(GLEISNAME_REGEXP, gleis)
        prefix = mo.group(1).replace(" ", "")
        try:
            nummer = int(mo.group(2))
        except ValueError:
            nummer = 0
        suffix = mo.group(3).replace(" ", "")
        return prefix, nummer, suffix

    def gleis_sektor_sortkey(self, gleis_sektor: Tuple[str, str]) -> Tuple[str, int, str, str, int, str]:
        """
        Hauptgleis und Sektorgleis in Sortierschlüssel umwandeln.

        Args:
            gleis_sektor: Tupel aus Hauptgleis und Sektorgleis.
                Sektorgleis, wie es im Fahrplan der Züge steht,
                Hauptgleis, wie es in der Anlagenkonfiguration steht.

        Returns:
            Tupel aus Präfix, Nummer, Suffix des Hauptgleises
            und darauf folgend Präfix, Nummer, Suffix des Sektorgleises,
            jeweils wie von gleisname_sortkey.
        """

        g1, g2, g3 = self.gleisname_sortkey(gleis_sektor[0])
        s1, s2, s3 = self.gleisname_sortkey(gleis_sektor[1])
        return g1, g2, g3, s1, s2, s3
