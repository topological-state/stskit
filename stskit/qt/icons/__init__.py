from PySide6.QtGui import QIcon
from iconipy import IconFactory

class ActionIcons:
    actions: dict[str, str] = {
        'actionSetup': 'settings-2',  # sliders-vertical
        'actionAnzeige': 'chart-gantt',  # 'chart-network',
        'actionBelegteGleise': 'panel-left-right-dashed',  # list-, square-, columns-, tally-
        'actionEinfacheGleise': 'columns-2',  #

        'actionPlusEins': 'clock-arrow-up',
        'actionMinusEins': 'clock-arrow-down',
        'actionFix': 'clock-alert',
        'actionVorzeitigeAbfahrt': 'wand',  # 'alarm-clock-off',  'circle-play',  # 'clock-fading',
        'actionVerspaetungLoeschen': 'undo',  # 'circle-off',  # off?

        'actionAnkunftAbwarten': 'git-branch',
        'actionAbfahrtAbwarten': 'git-merge',
        'actionKreuzung': 'git-compare-arrows',
        'actionZugfolge': 'git-pull-request-draft',
        'actionLoeschen': 'undo',
        'actionBetriebshaltEinfuegen': 'git-commit-vertical',
        'actionActionBetriebshaltLoeschen': 'undo',

        'actionAnschlussAbwarten': 'git-pull-request',  # 'git-branch-plus',
        'actionAnschlussAufgeben': 'git-pull-request-closed',  # 'git-branch-minus',

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
