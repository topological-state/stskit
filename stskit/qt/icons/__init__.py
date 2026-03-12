from PySide6 import QtGui
from PySide6.QtGui import QIcon
from iconipy import IconFactory

class ActionIcons:
    actions: dict[str, str] = {
        'actionSetup': 'settings',
        'actionAnzeige': 'chart-network',
        'actionBelegteGleise': 'train-track',
        'actionEinfacheGleise': 'train-track',

        'actionPlusEins': 'clock-arrow-up',
        'actionMinusEins': 'clock-arrow-down',
        'actionFix': 'clock-alert',
        'actionVorzeitigeAbfahrt': 'clock-fading',
        'actionVerspaetungLoeschen': 'circle-off',  # off?

        'actionAnkunftAbwarten': 'circle-chevron-left',  # 'git-merge',
        'actionAbfahrtAbwarten': 'circle-chevron-right',  # 'git-branch',
        'actionKreuzung': 'circle-x',  # 'git-compare',
        'actionZugfolge': 'circle-slash',  # 'git-pull-request-draft',
        'actionLoeschen': 'circle-off',
        'actionBetriebshaltEinfuegen': 'circle-parking',
        'actionActionBetriebshaltLoeschen': 'circle-parking-off',

        'actionAnschlussAbwarten': 'ticket-check',
        'actionAnschlussAufgeben': 'ticket-x',

        'actionWarnungSetzen': 'shield-alert',
        'actionWarnungIgnorieren': 'shield-check',
        'actionWarnungReset': 'shield-off',  # shield-minus, shield-ellipsis

        'actionZugAusblenden': 'eye-off',
        'actionZugEinblenden': 'eye',
    }

    def __init__(self):
        super().__init__()

        self._icon_factory_normal = IconFactory(icon_set='lucide',
                                                icon_size=16,
                                                font_size=16,
                                                font_color='white',
                                                background_color=(0x3f, 0x3f, 0x3f, 0xff), )
        self._icon_factory_disabled = IconFactory(icon_set='lucide',
                                                  icon_size=16,
                                                  font_size=16,
                                                  font_color='silver',
                                                  background_color=(0x3f, 0x3f, 0x3f, 0xff), )

        self._icons: dict[str, QIcon] = {}

    def get_icon(self, action: str) -> QIcon:
        try:
            key = self.actions.get(action)
        except KeyError:
            key = 'flame'

        icon = self._icons.get(key)
        if icon is None:
            icon = QIcon()
            normal_pixmap = self._icon_factory_normal.asQPixmap(key)
            icon.addPixmap(normal_pixmap, QIcon.Mode.Normal, QIcon.State.Off)
            disabled_pixmap = self._icon_factory_disabled.asQPixmap(key)
            icon.addPixmap(disabled_pixmap, QIcon.Mode.Disabled, QIcon.State.Off)
            self._icons[key] = icon

        return icon


action_icons = ActionIcons()
