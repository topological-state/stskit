"""
Gleischema: Übersetzung von Gleisnamen in Bahnhofnamen

Das Gleisschema ordnet den Gleisen einen Bahnsteig- und einen Bahnhofnamen zu.
Anschlussgleisen ordnet es eine Anschlussstelle zu.
Es ist mittels Konfigurationsdateien einstellbar.

"""

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
    alphabetischen anfang eines namens extrahieren.

    anfang des namens bis zum ersten nicht-alphabetischen zeichen (ziffer, leerzeichen, sonderzeichen).
    umlaute etc. werden als alphabetisch betrachtet.
    leerer string, wenn keine alphabetischen zeichen gefunden wurden.

    :param name: z.b. gleisname
    :return: resultat

    """
    return re.match(ALPHA_PREFIX_PATTERN, name).group(0)


class Gleisschema:
    REGISTRY = {}

    def __init__(self):
        self.region = 'default'
        self.schema = 'default'

    @staticmethod
    def regionsschema(region) -> 'Gleisschema':
        """
        Gleisschema anhand Region ermitteln und instanzieren.

        Der Name des Schemas wird zunächst anhand des ersten Wortes der Region ermittelt (REGIONEN_SCHEMA).
        Anschließend wird das in Gleisschema.REGISTRY registrierte Schema instanziiert.
        Wenn die Region nicht in der REGIONEN_SCHEMA-Liste enthalten ist, wird das Standardgleisschema verwendet.

        :param region: z.b. 'Berlin Ostbahnhof'
        :return: gleisschema
        """

        try:
            schema = REGIONEN_SCHEMA[region.split()[0]].lower()
        except (IndexError, KeyError):
            schema = 'default'
        cls = Gleisschema.REGISTRY.get(schema, Gleisschema)
        obj = cls()
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

        :param gleis: Gleisname (Bahnsteigname in der Plugin-Schnittstelle)
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

        FSP503 -> FSP
        NAH423b -> NAH
        6 -> Hbf
        10C-D -> Hbf
        BSGB D73 -> BSGB
        ZUE 12 -> ZUE
        BR 1b -> BR
        Lie W10 -> Lie
        Muntelier-L. -> Muntelier-L.
        VU3-5 -> VU
        Isola della Scala 3G -> Isola della Scala

        Beachte, dass Bahnhofs- und Gleisbezeichnungen Leerzeichen und Sonderzeichen enthalten können.
        In den folgenden Fällen (nicht abschliessend),
        liefert die Funktion nicht das gewünschte Ergebnis (in Klammern).

        Brennero: R3 -> R (Hbf), N -> N (Hbf)
        Drautal: Lie A1 -> Lie (Lie A1), Ma Wende R -> Ma Wende R (Ma)

        :param gleis: gleis- bzw. bahnsteigname
        :return: bahnhofname
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
            return "Hbf"

    def gleisname_kurz(self, gleis: str) -> str:
        """
        Gleisnamen abkürzen.

        Die Abkürzung wird in Grafiken verwendet, wo eine möglichst kurze Beschriftung verwendet werden soll.
        Das Resultat dieser Funktion ist nicht eindeutig und
        kann in der Programmlogik nicht als Gleisidentifikation verwendet werden.

        :param gleis: Gleis- bzw. Bahnsteigname
        :return: Gleisnummer (String), extrahiert aus Gleisnamen.
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
        prüft anhand von schlüsselwörtern, ob das gleis ein einfacher anschluss ist.

        zeigt True, wenn eine zeichenfolge aus EINZEL_ANSCHLUESSE im gleisnamen vorkommt.

        :param gleis: name des anschlussgleises
        :return:
        """
        for ea in EINZEL_ANSCHLUESSE:
            if gleis.find(ea) >= 0:
                return True

        return False

    def anschlussname(self, gleis: str) -> str:
        """
        anschlussname aus gleisnamen ableiten.

        es wird angenommen, dass der bahnhofname aus den alphabetischen zeichen am anfang des gleisnamens besteht.

        wenn der gleisname keine alphabetischen zeichen enthält
        oder eine zeichenfolge aus EINZEL_ANSCHLUESSE im gleisnamen vorkommt, wird der gleisname unverändert zurückgegeben.

        :param gleis: gleisname
        :return: anschlussname
        """

        if self.ist_einzel_anschluss(gleis):
            return gleis
        else:
            anschluss = NON_DIGIT_PREFIX_PATTERN.match(gleis).group(0).strip()
            if anschluss:
                return anschluss
            else:
                return gleis
