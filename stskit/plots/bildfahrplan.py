import math
import logging
from typing import Any, Dict, List, Optional, Tuple

import matplotlib as mpl
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.image import AxesImage
from matplotlib.text import Text
import networkx as nx

from stskit.utils.observer import Observable
from stskit.model.bahnhofgraph import BahnhofLabelType
from stskit.model.ereignisgraph import EreignisGraph, EreignisGraphNode, EreignisGraphEdge, EreignisLabelType
from stskit.model.zielgraph import ZielLabelType
from stskit.model.zuggraph import ZugGraphNode
from stskit.plugin.stsobj import format_verspaetung, format_minutes
from stskit.plots.plotbasics import hour_minutes_formatter
from stskit.model.zugschema import Zugbeschriftung
from stskit.zentrale import DatenZentrale


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def format_label(zugbeschriftung: Zugbeschriftung, zug: ZugGraphNode, anfang: EreignisGraphNode, ende: EreignisGraphNode):
    """
    zuglabel formatieren mit verspätungsangabe

    das label besteht aus zugname und verspätungsangabe (falls nicht null).
    die verspätungsangabe besteht aus einem teil wenn sie am anfang und ende der linie gleich ist,
    sonst aus der verspätung am anfang und ende.

    :param plan1: anfangspunkt der linie. zug.name und verspaetung_ab werden benutzt.
    :param plan2: endpunkt der linie. verspaetung_an wird benutzt.
    :return: (str)
    """

    try:
        v1 = anfang.t_eff - anfang.t_plan
    except AttributeError:
        v1 = None
    try:
        v2 = ende.t_eff - ende.t_plan
    except AttributeError:
        v2 = None
    if v1 is None:
        v1 = v2 or 0
    if v2 is None:
        v2 = v1 or 0

    if "Name" in zugbeschriftung.elemente:
        name = zug.name
    elif "Nummer" in zugbeschriftung.elemente:
        name = zug.nummer
    else:
        name = ""

    if v1 == v2:
        if v1 == 0:
            v = ""
        else:
            v = format_verspaetung(v1)
    else:
        v = "|".join((format_verspaetung(v1), format_verspaetung(v2)))

    if v:
        return f"{name} ({v})"
    else:
        return f"{name}"


def format_zuginfo(zug: ZugGraphNode, abfahrt: EreignisGraphNode, ankunft: EreignisGraphNode):
    """
    zug-trasseninfo formatieren

    beispiel:
    ICE 573 A-D: B 2 ab 15:30 +3, C 3 an 15:40 +3

    :param trasse: ausgewaehlte trasse
    :return: (str)
    """

    z1 = format_minutes(abfahrt.t_plan)
    z2 = format_minutes(ankunft.t_plan)
    v1 = f"{abfahrt.t_eff - abfahrt.t_plan:+}"
    v2 = f"{ankunft.t_eff - ankunft.t_plan:+}"
    name = zug.name
    von = zug.von
    nach = zug.nach

    return f"{name} ({von} - {nach}): {abfahrt.gleis} ab {z1}{v1}, {ankunft.gleis} an {z2}{v2}"


class BildfahrplanPlot:
    def __init__(self, zentrale: DatenZentrale, canvas: mpl.backend_bases.FigureCanvasBase):
        self.zentrale = zentrale
        self.anlage = zentrale.anlage

        self.strecken_name: str = ""
        self.strecke_von: str = ""
        self.strecke_via: str = ""
        self.strecke_nach: str = ""
        self.zugbeschriftung = Zugbeschriftung(stil="Bildfahrplan")

        self.bildgraph = EreignisGraph()
        self.streckengraph = nx.MultiDiGraph()

        # bahnhofname -> distanz [minuten]
        self.strecke: List[BahnhofLabelType] = []
        self.distanz: List[float] = []
        # ortskoordinate der segmentmitte -> linker bahnhof
        self.naechster_bahnhof: Dict[float, BahnhofLabelType] = {}

        self.zeit = 0
        self.vorlaufzeit = 55
        self.nachlaufzeit = 5

        self.auswahl_geaendert = Observable(self)
        self.auswahl_text: List[str] = []
        self.auswahl_kanten: List[Tuple[EreignisLabelType, ...]] = []
        self.auswahl_bahnhoefe: List[BahnhofLabelType] = []

        self._canvas = canvas
        self._axes = self._canvas.figure.subplots()
        self._pick_event: bool = False
        self._canvas.mpl_connect("button_press_event", self.on_button_press)
        self._canvas.mpl_connect("button_release_event", self.on_button_release)
        self._canvas.mpl_connect("pick_event", self.on_pick)
        self._canvas.mpl_connect("resize_event", self.on_resize)


    def _bahnhof_von_gleis(self, plan, zug):
        try:
            gleis1 = ('Gl', plan.gleis)
            gruppe1 = self.anlage.bahnhofgraph.find_superior(gleis1, {'Bf'})
        except (KeyError, nx.NetworkXError):
            gleis1 = ('Agl', plan.gleis)
            try:
                gruppe1 = self.anlage.bahnhofgraph.find_superior(gleis1, {'Anst'})
            except (KeyError, nx.NetworkXError):
                logger.warning(f"gleis {plan.gleis} ({zug.name}) kann keinem bahnhof zugeordnet werden.")
                gruppe1 = ""
        return gruppe1

    def default_strecke_waehlen(self):
        """
        Hauptstrecke auswählen.

        Die Hauptstrecke ist in der Anlage eingestellt.
        Wenn keine Hauptstrecke definiert ist, wird die längste Strecke der Anlage übernommen.

        Die Attribute strecken_name, strecke_von, strecke_nach und strecke_via werden entsprechend aktualisiert.
        Ruft ausserdem update_strecke() auf.

        :return: None
        """

        strecken = [(name, len(strecke)) for name, strecke in self.anlage.strecken.items()]
        try:
            laengste_strecke = max(strecken, key=lambda x: x[1])
            laengste_strecke = laengste_strecke[0]
        except (ValueError, IndexError):
            laengste_strecke = ""

        try:
            self.strecken_name = self.anlage.hauptstrecke
            strecke = self.anlage.strecken[self.anlage.hauptstrecke]
        except KeyError:
            self.strecken_name = ""
            try:
                strecke = self.anlage.strecken[laengste_strecke]
            except KeyError:
                strecke = []

        try:
            self.strecke_von = strecke[0][1]
            self.strecke_nach = strecke[-1][1]
            self.strecke_via = ""
        except IndexError:
            self.strecke_von = ""
            self.strecke_nach = ""
            self.strecke_via = ""

        self.update_strecke()

    def update_strecke(self):
        """
        Strecke berechnen.

        Berechnet die Strecke, Distanzen und den Streckengraphen.
        Muss nach jeder Änderung der Streckenattribute (strecke_name, strecke_von, etc.) aufgerufen werden.

        :return: None
        """

        self.streckengraph.clear()

        if self.strecken_name in self.anlage.strecken:
            strecke = self.anlage.strecken[self.strecken_name]
            try:
                self.strecke_von = strecke[0][1]
                self.strecke_nach = strecke[-1][1]
            except IndexError:
                self.strecke_von = ""
                self.strecke_nach = ""
            self.strecke_via = ""

        elif self.strecke_von and self.strecke_nach:
            if self.strecke_via:
                von_gleis = self.strecke_von
                nach_gleis = self.strecke_via
                strecke1 = self.anlage.liniengraph.strecke(von_gleis, nach_gleis)
                von_gleis = self.strecke_via
                nach_gleis = self.strecke_nach
                strecke2 = self.anlage.liniengraph.strecke(von_gleis, nach_gleis)
                strecke = [*strecke1[:-1], *strecke2]
            else:
                von_gleis = self.strecke_von
                nach_gleis = self.strecke_nach
                strecke = self.anlage.liniengraph.strecke(von_gleis, nach_gleis)

        else:
            strecke = []

        self.strecke = strecke
        if strecke:
            sd = self.anlage.liniengraph.strecken_zeitachse(strecke, parameter='fahrzeit_schnitt')
            self.distanz = sd

            for ia, a in enumerate(zip(self.strecke, self.distanz)):
                for ib, b in enumerate(zip(self.strecke[ia:], self.distanz[ia:])):
                    if a[0] != b[0] or ib == 0:
                        self.streckengraph.add_edge(a[0], b[0], s0=a[1], s1=b[1])
                        self.streckengraph.add_edge(b[0], a[0], s0=b[1], s1=a[1])
                    else:
                        break
        else:
            self.distanz = []

        try:
            mitten = [(s1 + s2) / 2 for s1, s2 in zip(self.distanz[:-1], self.distanz[1:])]
            mitten.append(self.distanz[-1] + (self.distanz[-1] - self.distanz[-2]) / 2)
        except IndexError:
            mitten = []
        self.naechster_bahnhof = {s: bf for s, bf in zip(mitten, self.strecke)}

    def update_ereignisgraph(self):
        """
        Zuege aus Ereignisgrpah uebernhemen.

        - bst aufloesen
        - zuege nach zeit filtern
        - zuege nach strecke filtern
        - koordinaten ausrechnen
        - Grafikstil bestimmen

        Verwendete Marker
        -----------------

        '.' (Punkt) Planmaessiger Halt
        '*' (Stern) E/F/K
        'P' (fettes plus) Betriebshalt

        Verwendete Linienstile
        ----------------------

        ':' (gepunktet) Halt
        '-' (ausgezogen) Fahrt
        """

        def bst_von_fid(fid: ZielLabelType) -> Optional[BahnhofLabelType]:
            try:
                gl = self.anlage.bahnhofgraph.ziel_gleis[fid[-1]]
                bst = self.anlage.bahnhofgraph.find_superior(gl, {'Bf', 'Anst'})
                return bst
            except (IndexError, KeyError):
                return None

        def bst_von_gleis(gl: str) -> Optional[BahnhofLabelType]:
            try:
                bst = self.anlage.bahnhofgraph.find_name(gl)
                bst = self.anlage.bahnhofgraph.find_superior(bst, {'Bf', 'Anst'})
                return bst
            except (IndexError, KeyError):
                return None

        def _add_node(ereignis_label, ereignis_data):
            bst = bst_von_gleis(ereignis_data.gleis)
            if bst in strecke:
                zug = self.anlage.zuggraph.nodes[ereignis_data.zid]
                d = ereignis_data.copy()
                d['bst'] = bst
                d['farbe'] = self.anlage.zugschema.zugfarbe(zug)
                d['marker'] = '.'
                self.bildgraph.add_node(ereignis_label, **d)

        self.bildgraph.clear()
        t0 = self.zeit - self.nachlaufzeit
        t1 = self.zeit + self.vorlaufzeit

        strecke = set(self.strecke)

        for node, data in self.anlage.ereignisgraph.nodes(data=True):
            try:
                if t0 <= data.t_eff <= t1:
                    _add_node(node, data)
            except AttributeError:
                continue

        for u, v, data in self.anlage.ereignisgraph.edges(data=True):
            if u in self.bildgraph or v in self.bildgraph:
                zug = self.anlage.zuggraph.nodes[data.zid]
                u_data = self.anlage.ereignisgraph.nodes[u]
                v_data = self.anlage.ereignisgraph.nodes[v]
                u_v_data = data.copy()
                u_v_data['farbe'] = self.anlage.zugschema.zugfarbe(zug)
                u_v_data['titel'] = format_label(self.zugbeschriftung, zug, u_data, v_data)
                u_v_data['fontstyle'] = "normal"
                u_v_data['linewidth'] = 1
                u_v_data['linestyle'] = ':' if data.typ in {"B", "E", "F", "H"} else "-"

                if u not in self.bildgraph:
                    _add_node(u, u_data)
                if v not in self.bildgraph:
                    _add_node(v, v_data)
                self.bildgraph.add_edge(u, v, **u_v_data)

                if data.typ == "B":
                    self.bildgraph.nodes[v]['marker'] = 'P'

    def line_args(self, start: EreignisGraphNode, ziel: EreignisGraphNode, data: EreignisGraphEdge) -> Dict[str, Any]:
        args = {'color': data.farbe,
                'linewidth': data.linewidth,
                'linestyle': data.linestyle,
                'marker': start.marker}

        try:
            args['markevery'] = [start.typ == "Ab" or data.typ in {"E", "F", "H"}, data.typ == "H"]
        except AttributeError:
            args['marker'] = ""

        try:
            if data.auswahl == 1:
                args['color'] = 'yellow'
                args['alpha'] = 0.5
                args['linewidth'] = 2
            elif data.auswahl == 2:
                args['color'] = 'cyan'
                args['alpha'] = 0.5
                args['linewidth'] = 2
        except AttributeError:
            pass

        return args

    def marker_args(self, start: EreignisGraphNode) -> Dict[str, Any]:
        args = {'c': start.farbe}

        try:
            if start.typ == "Ab":
                args['marker'] = start.marker
            elif start.typ in {"E", "F", "K"}:
                args['marker'] = "*"
            else:
                args['marker'] = ""
        except AttributeError:
            args['marker'] = ""

        return args

    def draw_graph(self):
        self._axes.clear()

        x_labels = [s for _, s in self.strecke]
        x_labels_pos = self.distanz

        self._axes.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='right')
        self._axes.yaxis.set_major_formatter(hour_minutes_formatter)
        self._axes.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._axes.yaxis.set_major_locator(mpl.ticker.MultipleLocator(5))
        self._axes.yaxis.grid(True, which='major')
        self._axes.xaxis.grid(True)

        ylim = (self.zeit - self.nachlaufzeit, self.zeit + self.vorlaufzeit)
        self._axes.set_ylim(top=ylim[0], bottom=ylim[1])
        try:
            self._axes.set_xlim(left=x_labels_pos[0], right=x_labels_pos[-1])
        except IndexError:
            return

        try:
            idx = x_labels.index(self.strecke_via)
        except ValueError:
            pass
        else:
            self._axes.axvline(x=self.distanz[idx], color=mpl.rcParams['grid.color'],
                               linewidth=mpl.rcParams['axes.linewidth'])

        wid_x = x_labels_pos[-1] - x_labels_pos[0]
        wid_y = self.nachlaufzeit + self.vorlaufzeit
        off_x = 0
        off = self._axes.transData.inverted().transform([(0, 0), (0, -5)])
        off_y = (off[1] - off[0])[1]

        self._strecken_markieren(x_labels, x_labels_pos)

        label_args = {'ha': 'center',
                      'va': 'center',
                      'fontsize': 'small',
                      'fontstretch': 'condensed',
                      'rotation_mode': 'anchor',
                      'transform_rotates_text': True}

        for u, v, data in self.bildgraph.edges(data=True):
            u_data = self.bildgraph.nodes[u]
            v_data = self.bildgraph.nodes[v]

            try:
                for s_u, s_v, s_key, s_data in self.streckengraph.edges(u_data.bst, keys=True, data=True):
                    if s_v == v_data.bst:
                        pos_x = [s_data['s0'], s_data['s1']]
                        pos_y = [u_data.t_eff, v_data.t_eff]
                        mpl_lines = self._axes.plot(pos_x, pos_y,
                                                    picker=True,
                                                    pickradius=5,
                                                    **self.line_args(u_data, v_data, data))
                        mpl_lines[0].edge = (u, v, s_key)

                        seg = [[pos_x[0], pos_y[0]], [pos_x[1], pos_y[1]]]
                        pix = self._axes.transData.transform(seg)
                        cx = (seg[0][0] + seg[1][0]) / 2 + off_x
                        cy = (seg[0][1] + seg[1][1]) / 2 + off_y
                        dx = (seg[1][0] - seg[0][0])
                        dy = (seg[1][1] - seg[0][1])
                        if ylim[0] < cy < ylim[1]:
                            if abs(pix[1][0] - pix[0][0]) > 30:
                                try:
                                    ang = math.degrees(math.atan(dy / dx))
                                except ZeroDivisionError:
                                    pass
                                else:
                                    self._axes.text(cx, cy, data.titel, rotation=ang, **label_args)
            except AttributeError as e:
                logger.debug("Fehlendes Attribut im Bildgraph beim Kantenzeichnen", exc_info=e)

        for u in self.bildgraph.nodes(data=False):
            u_data = self.bildgraph.nodes[u]
            try:
                if u_data.typ in {"E", "F", "K"}:
                    for s_u, s_v, s_key, s_data in self.streckengraph.edges(u_data.bst, keys=True, data=True):
                        if s_v == u_data.bst:
                            pos_x = s_data['s0']
                            pos_y = u_data.t_eff
                            self._axes.scatter(pos_x, pos_y, **self.marker_args(u_data))
            except AttributeError as e:
                logger.debug("Fehlendes Attribut im Bildgraph beim Knotenzeichnen", exc_info=e)

        for item in (self._axes.get_xticklabels() + self._axes.get_yticklabels()):
            item.set_fontsize('small')

        if self.nachlaufzeit > 0:
            self._axes.axhline(y=self.zeit,
                               color=mpl.rcParams['axes.edgecolor'],
                               linewidth=mpl.rcParams['axes.linewidth'])

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def _strecken_markieren(self, x_labels, x_labels_pos):
        """
        strecken mit einer schraffur markieren

        :param x_labels: liste von gleisnamen
        :param x_labels_pos: liste von x-koordinaten der gleise
        :param kwargs: kwargs-dict, der für die axes.bar-methode vorgesehen ist.
        :return: None
        """

        try:
            markierungen = self.anlage.streckenmarkierung
        except AttributeError:
            markierungen = {}

        ylim = self._axes.get_ylim()
        h = max(ylim) - min(ylim)
        for strecke, art in markierungen.items():
            try:
                x1 = x_labels_pos[x_labels.index(strecke[0][1])]
                x2 = x_labels_pos[x_labels.index(strecke[1][1])]
                xy = (x1, min(ylim))
                w = x2 - x1
            except ValueError:
                continue

            color = mpl.rcParams['grid.color']
            r = mpl.patches.Rectangle(xy, w, h, color=color, alpha=0.1, linewidth=None)
            self._axes.add_patch(r)

    def on_resize(self, event):
        """
        Matplotlib Resize-Event

        Zeichnet die Grafik neu.

        :param event:
        :return:
        """

        self.draw_graph()


    def on_button_press(self, event):
        """
        Matplotlib Button-Press Event

        Aktualisiert die Grafik, wenn zuvor ein Pick-Event stattgefunden hat.
        Wenn kein Pick-Event stattgefunden hat, wird die aktuelle Trassenauswahl gelöscht.

        :param event:
        :return:
        """

        if self._pick_event:
            self.draw_graph()
        else:
            self.clear_selection()
            self.draw_graph()

        self._pick_event = False
        self.auswahl_geaendert.notify()

    def on_button_release(self, event):
        """
        Matplotlib Button-Release Event

        Hat im Moment keine Wirkung.

        :param event:
        :return:
        """

        pass

    def on_pick(self, event):
        """
        Matplotlib Pick-Event wählt Liniensegmente (Trassen) aus oder ab

        Die Auswahl wird in _selected_edges gespeichert.
        Es können maximal zwei Trassen gewählt sein.

        :param event:
        :return:
        """

        if event.mouseevent.inaxes == self._axes:
            self._pick_event = True
            if isinstance(event.artist, Line2D):
                try:
                    edge = event.artist.edge
                except AttributeError:
                    return
                else:
                    self.select_edge(edge[0], edge[1], event.mouseevent.xdata, event.mouseevent.ydata)
            elif isinstance(event.artist, Text):
                pass

            self.auswahl_text = [self.format_zuginfo(*tr) for tr in self.auswahl_kanten]

    def select_edge(self,
                    u: EreignisLabelType,
                    v: EreignisLabelType,
                    x: Optional[float],
                    t: Optional[float]):
        """
        Zugtrasse selektieren

        Die Trasse wird zusätzlich zu ev. bereits ausgewählten Trassen ausgewählt.
        Die erste Trasse erhält das auswahl-Attribut 1, die weiteren 2.
        Der Aufrufer bestimmt, wie viele Trassen ausgewählt sein dürfen.
        Um Trassen zu deselektieren, die clear_selection-Methode aufrufen.

        Die Grafik wird nicht aktualisiert.
        Observers werden nicht benachrichtigt.

        :param u: Ausgangspunkt der Trasse im Ereignisgraph
        :param v: Zielpunkt der Trasse im Ereignisgraph
        :param x: Ortskoordinate des Mausklicks
        :param t: Zeitkoordinate des Mausklicks (im Moment nicht verwendet)
        :return: None
        """

        bahnhof = None
        if x is not None:
            for s, bf in self.naechster_bahnhof.items():
                if x < s:
                    bahnhof = bf
                    break

        edge_data = self.bildgraph.get_edge_data(u, v)
        if edge_data is not None and bahnhof is not None:
            self.auswahl_kanten.append((u, v))
            self.auswahl_bahnhoefe.append(bahnhof)
            idx = min(2, len(self.auswahl_kanten))
            edge_data.auswahl = idx

    def clear_selection(self):
        """
        Trassenauswahl löschen

        Löscht alle gewählten Trassen.
        Die Grafik wird nicht aktualisiert.
        Observers werden nicht benachrichtigt.
        """

        for edge in self.auswahl_kanten:
            edge_data = self.bildgraph.get_edge_data(*edge)
            if edge_data is not None:
                edge_data.auswahl = 0

        self.auswahl_kanten = []
        self.auswahl_bahnhoefe = []
        self.auswahl_text = []

    def format_zuginfo(self, u: EreignisLabelType, v: EreignisLabelType):
        """
        Zugtrasseninfo formatieren

        Beispiel:
        ICE 573 A-D: B 2 ab 15:30 +3, C 3 an 15:40 +3

        :param u: Ausgangspunkt der Trasse im Ereignisgraph
        :param v: Zielpunkt der Trasse im Ereignisgraph
        :return: (str)
        """

        abfahrt = self.bildgraph.nodes[u]
        ankunft = self.bildgraph.nodes[v]

        try:
            zug = self.zentrale.anlage.zuggraph.nodes[abfahrt.zid]
            name = zug.name
            von = zug.von
            nach = zug.nach
        except KeyError:
            name = f"[{abfahrt.zid}]"
            von = "?"
            nach = "?"

        z1 = format_minutes(abfahrt.t_eff)
        z2 = format_minutes(ankunft.t_eff)
        v1 = format_verspaetung(round(abfahrt.t_eff - abfahrt.t_plan))
        v2 = format_verspaetung(round(ankunft.t_eff - ankunft.t_plan))

        return f"{name} ({von} - {nach}): {abfahrt.gleis} ab {z1}{v1}, {ankunft.gleis} an {z2}{v2}"
