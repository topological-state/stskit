import re
import logging
from typing import Any, Dict, Generator, Iterable, List, Mapping, Set, Tuple


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def common_prefix(lst: Iterable) -> Generator[str, None, None]:
    for s in zip(*lst):
        if len(set(s)) == 1:
            yield s[0]
        else:
            return


def gemeinsamer_name(g: Iterable) -> str:
    return ''.join(common_prefix(g)).strip()


# \d digit
# \s whitespace
# \w word/alphanumeric including underscore

ALPHA_PREFIX_PATTERN = re.compile(r'[^\d\W]*')
NON_DIGIT_PREFIX_PATTERN = re.compile(r'\D*')
ALPHANUMERISCHES_GLEIS_PATTERN = re.compile(r'([^\d\W]*)\s*(\w*)')
ENTHAELT_ZIFFER_REGEX = re.compile(r'\D*\d+\D*')
BAHNSTEIG_VON_SEKTOR_REGEX = re.compile(r'\D*\d+')

EINZEL_ANSCHLUESSE = ['Anschluss', 'Feld', 'Gruppe', 'Gleis', 'Gr.', 'Anschl.', 'Gl.', 'Industrie', 'Depot', 'Abstellung']


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


def default_bahnsteigname(gleis: str) -> str:
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


def default_bahnhofname(gleis: str) -> str:
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


def ist_einzel_anschluss(gleis: str) -> bool:
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


def default_anschlussname(gleis: str) -> str:
    """
    anschlussname aus gleisnamen ableiten.

    es wird angenommen, dass der bahnhofname aus den alphabetischen zeichen am anfang des gleisnamens besteht.

    wenn der gleisname keine alphabetischen zeichen enthält
    oder eine zeichenfolge aus EINZEL_ANSCHLUESSE im gleisnamen vorkommt, wird der gleisname unverändert zurückgegeben.

    :param gleis: gleisname
    :return: anschlussname
    """

    if ist_einzel_anschluss(gleis):
        return gleis
    else:
        anschluss = NON_DIGIT_PREFIX_PATTERN.match(gleis).group(0).strip()
        if anschluss:
            return anschluss
        else:
            return gleis
