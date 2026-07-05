from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .conexion import main


class InfoSIPEB:

    def __init__(self, iface):
        self.iface = iface
        self.action = None

    def initGui(self):

        self.action = QAction(
            QIcon(""),
            "INFO-SIPEB",
            self.iface.mainWindow()
        )

        self.action.triggered.connect(main)

        # Solo aparece en el menú Complementos
        self.iface.addPluginToMenu(
            "&INFO-SIPEB",
            self.action
        )

    def unload(self):

        self.iface.removePluginMenu(
            "&INFO-SIPEB",
            self.action
        )
