from pathlib import Path

try:
    from qgis.PyQt.QtGui import QAction, QIcon
except ImportError:
    from qgis.PyQt.QtGui import QIcon
    from qgis.PyQt.QtWidgets import QAction

from .conexion import main


class InfoSIPEB:

    def __init__(self, iface):
        self.iface = iface
        self.action = None

    def initGui(self):
        icon_path = Path(__file__).parent / "icon.png"

        self.action = QAction(
            QIcon(str(icon_path)) if icon_path.exists() else QIcon(),
            "INFO-SIPEB",
            self.iface.mainWindow()
        )

        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(
            "&INFO-SIPEB",
            self.action
        )

    def run(self, checked=False):
        main(self.iface)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(
                "&INFO-SIPEB",
                self.action
            )
            self.action = None
