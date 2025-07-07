import math
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import matplotlib as mpl
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.image import AxesImage
from matplotlib.text import Text
import networkx as nx

from stskit.utils.observer import Observable
from stskit.model.bahnhofgraph import BahnhofElement
from stskit.model.ereignisgraph import EreignisGraph, EreignisGraphNode, EreignisGraphEdge, EreignisLabelType
from stskit.model.zuggraph import ZugGraphNode
from stskit.plugin.stsobj import format_verspaetung, format_minutes
from stskit.plots.plotbasics import hour_minutes_formatter
from stskit.model.zugschema import Zugbeschriftung
from stskit.zentrale import DatenZentrale


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class BildfahrplanPlot:
    def __init__(self, zentrale: DatenZentrale, canvas: mpl.backend_bases.FigureCanvasBase):
        self.zentrale = zentrale
        self.anlage = zentrale.anlage

        self.strecken_name: str = ""
        self.strecke_von: Optional[BahnhofElement] = None
        self.strecke_via: Optional[BahnhofElement] = None
        self.strecke_nach: Optional[BahnhofElement] = None
        self.zugbeschriftung = Zugbeschriftung(self.zentrale.anlage)

        self.bildgraph = EreignisGraph()
        self.streckengraph = nx.MultiDiGraph()

        # bahnhofname -> distanz [minuten]
        self.strecke: List[BahnhofElement] = []
        self.distanz: List[float] = []
        self.linienstil: List[str] = []
        # ortskoordinate der segmentmitte -> linker bahnhof
        self.naechster_bahnhof: Dict[float, BahnhofElement] = {}

        self.zeit = 0
        self.vorlaufzeit = 55
        self.nachlaufzeit = 5

        self.auswahl_geaendert = Observable(self)
        self.auswahl_text: List[str] = []
        self.auswahl_kanten: List[Tuple[EreignisLabelType, ...]] = []
        self.auswahl_bahnhoefe: List[BahnhofElement] = []

        self._canvas = canvas
        self._axes = self._canvas.figure.subplots()
        self._pick_event: bool = False
        self._canvas.mpl_connect("button_press_event", self.on_button_press)
        self._canvas.mpl_connect("button_release_event", self.on_button_release)
        self._canvas.mpl_connect("pick_event", self.on_pick)
        self._canvas.mpl_connect("resize_event", self.on_resize)


    def default_strecke_waehlen(self):
        """
        Hauptstrecke auswählen.

        Die Hauptstrecke ist in der Anlage eingestellt.
        Wenn keine Hauptstrecke definiert ist, wird die längste Strecke der Anlage übernommen.

        Die Attribute strecken_name, strecke_von, strecke_nach und strecke_via werden entsprechend aktualisiert.
        Ruft ausserdem update_strecke() auf.

        :return: None
        """

        strecken = [(name, len(strecke)) for name, strecke in self.anlage.strecken.strecken.items()]
        try:
            laengste_strecke = max(strecken, key=lambda x: x[1])
            laengste_strecke = laengste_strecke[0]
        except (ValueError, IndexError):
            laengste_strecke = ""

        try:
            self.strecken_name = self.anlage.strecken.hauptstrecke
            strecke = self.anlage.strecken.strecken[self.anlage.strecken.hauptstrecke]
        except KeyError:
            self.strecken_name = ""
            try:
                strecke = self.anlage.strecken.strecken[laengste_strecke]
            except KeyError:
                strecke = []

        try:
            self.strecke_von = strecke[0]
            self.strecke_nach = strecke[-1]
            self.strecke_via = None
        except IndexError:
            self.strecke_von = None
            self.strecke_nach = None
            self.strecke_via = None

        self.update_strecke()

    def update_strecke(self):
        """
        Strecke berechnen.

        Berechnet die Strecke, Distanzen und den Streckengraphen.
        Muss nach jeder Änderung der Streckenattribute (strecke_name, strecke_von, etc.) aufgerufen werden.

        :return: None
        """

        self.streckengraph.clear()

        if self.strecken_name in self.anlage.strecken.strecken:
            strecke = self.anlage.strecken.strecken[self.strecken_name]
            try:
                self.strecke_von = strecke[0]
                self.strecke_nach = strecke[-1]
            except IndexError:
                self.strecke_von = None
                self.strecke_nach = None
            self.strecke_via = None

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

            self.linienstil = [self.anlage.bahnhofgraph.nodes.get(s, {}).get('linienstil', ':') for s in self.strecke]
        else:
            self.distanz = []
            self.linienstil = []

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

        '.' (Punkt) Planmässiger Halt
        '*' (Stern) E/F/K
        'P' (fettes plus) Betriebshalt
        'v' (Dreieck unten) abhängiger Halt

        Verwendete Linienstile
        ----------------------

        '--' (gestrichelt) Halt
        '-' (ausgezogen) Fahrt
        ':' (gepunktet) Abhängigkeit
        """

        def bst_von_gleis(gl: Union[str, BahnhofElement]) -> Optional[BahnhofElement]:
            try:
                if isinstance(gl, BahnhofElement):
                    bst = gl
                else:
                    bst = self.anlage.bahnhofgraph.find_name(gl)
                if bst.typ not in {'Bf', 'Anst'}:
                    bst = self.anlage.bahnhofgraph.find_superior(bst, {'Bf', 'Anst'})
                if bst in strecke:
                    return bst
                else:
                    return None
            except (AttributeError, IndexError, KeyError) as e:
                logger.error(f"Error in bst_von_gleis: {gl} -> {bst}", exc_info=e)
                return None

        def _add_node(ereignis_label, ereignis_data, bst):
            zug = self.anlage.zuggraph.nodes[ereignis_data.zid]
            d = ereignis_data.copy()
            d['bst'] = bst
            d['farbe'] = self.anlage.zugschema.zugfarbe(zug)
            d['marker'] = '.'
            self.bildgraph.add_node(ereignis_label, **d)

        self.bildgraph.clear()
        t0 = self.zeit - self.nachlaufzeit - 10
        t1 = self.zeit + self.vorlaufzeit + 10

        strecke = set(self.strecke)

        for node, data in self.anlage.ereignisgraph.nodes(data=True):
            try:
                if t0 <= data.t_eff <= t1:
                    bst = bst_von_gleis(data.gleis)
                    if bst is not None:
                        _add_node(node, data, bst)
            except AttributeError:
                continue

        for u, v, data in self.anlage.ereignisgraph.edges(data=True):
            if data.typ in {'P', 'H', 'B', 'E', 'F', 'K', 'A'} and (u in self.bildgraph or v in self.bildgraph):
                zug = self.anlage.zuggraph.nodes[data.zid]
                u_data = self.anlage.ereignisgraph.nodes[u]
                v_data = self.anlage.ereignisgraph.nodes[v]
                u_v_data = data.copy()
                u_v_data['farbe'] = self.anlage.zugschema.zugfarbe(zug)
                u_v_data['titel'] = self.zugbeschriftung.format_trasse_label(zug, abfahrt=u_data, ankunft=v_data)
                u_v_data['fontstyle'] = "normal"
                u_v_data['linewidth'] = 1
                u_v_data['linestyle'] = '--' if data.typ in {"B", "E", "F", "H"} else "-"
                if data.typ == 'A':
                    u_v_data['linestyle'] = ':'
                    u_v_data['farbe'] = 'silver'

                if u not in self.bildgraph:
                    bst = bst_von_gleis(u_data.gleis_bst or u_data.gleis)
                    if bst is not None:
                        _add_node(u, u_data, bst)
                    else:
                        continue
                if v not in self.bildgraph:
                    bst = bst_von_gleis(v_data.gleis_bst or v_data.gleis)
                    if bst is not None:
                        _add_node(v, v_data, bst)
                    else:
                        continue
                self.bildgraph.add_edge(u, v, **u_v_data)

                if data.typ == "B":
                    self.bildgraph.nodes[v]['marker'] = 'P'
                elif data.typ == 'A':
                    self.bildgraph.nodes[v]['marker'] = 'v'

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

        ylim = (self.zeit - self.nachlaufzeit, self.zeit + self.vorlaufzeit)
        self._axes.set_ylim(top=ylim[0], bottom=ylim[1])
        try:
            self._axes.set_xlim(left=x_labels_pos[0], right=x_labels_pos[-1])
        except IndexError:
            return

        self._stationen_markieren(x_labels, x_labels_pos, self.linienstil)
        self._strecken_markieren(x_labels, x_labels_pos)
        if self.nachlaufzeit > 0:
            self._axes.axhline(y=self.zeit,
                               color=mpl.rcParams['axes.edgecolor'],
                               linewidth=mpl.rcParams['axes.linewidth'])

        wid_x = x_labels_pos[-1] - x_labels_pos[0]
        wid_y = self.nachlaufzeit + self.vorlaufzeit
        off_x = 0
        off = self._axes.transData.inverted().transform([(0, 0), (0, -5)])
        off_y = (off[1] - off[0])[1]

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
                logger.debug(u)
                logger.debug(u_data)
                logger.debug(v)
                logger.debug(v_data)

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

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def _stationen_markieren(self,
                             x_labels: Sequence[str],
                             x_labels_pos: Sequence[Union[int, float]],
                             x_labels_stil: Optional[Sequence[str]]):
        """
        Stationen mit vertikalen Linien markieren

        :param x_labels: Liste von Bahnhof- oder Anschlussnamen (Bf oder Anst Typ)
        :param x_labels_pos: Liste von x-Koordinaten der Stationen
        :param x_labels_stil: Matplotlib-Linienstil (z.B. '-', '--', ':', '').
            Bei leerem String wird keine Linie gezeichnet.
            Bei einem String mit 'w', wird die Linie weiß gezeichnet.
        :return: None
        """

        if not x_labels_stil:
            x_labels_stil = [':' for _ in x_labels]
        for label, pos, stil in zip(x_labels, x_labels_pos, x_labels_stil):
            if label == self.strecke_via:
                stil = '-'
            if stil:
                color = mpl.rcParams['axes.edgecolor'] if 'w' in stil else mpl.rcParams['grid.color']
                self._axes.axvline(x=pos,
                                   color=color,
                                   linestyle=stil.replace('w', ''),
                                   linewidth=mpl.rcParams['axes.linewidth'])

    def _strecken_markieren(self, x_labels, x_labels_pos):
        """
        strecken mit einer schraffur markieren

        :param x_labels: liste von gleisnamen
        :param x_labels_pos: liste von x-koordinaten der gleise
        :param kwargs: kwargs-dict, der für die axes.bar-methode vorgesehen ist.
        :return: None
        """

        try:
            markierungen = {(e1, e2): m for e1, e2, m in self.anlage.liniengraph.edges(data='markierung') if m}
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
        except KeyError:
            info = f"[{abfahrt.zid}]"
        else:
            info = self.zugbeschriftung.format_trasse_info(zug, ankunft=ankunft, abfahrt=abfahrt)

        return info
