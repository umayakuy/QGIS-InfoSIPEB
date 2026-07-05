# -*- coding: utf-8 -*-
import re
import zipfile
from pathlib import Path

import requests

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsWkbTypes,
)

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QProgressBar,
)


# Compatibilidad Qt 5 / Qt 6.
# QGIS 3 usa Qt 5 y QGIS 4 usa Qt 6; qgis.PyQt permite mantener
# una sola base de código, pero algunos enums cambiaron de ubicación.
def qt_enum(grupo, nombre):
    enum_grupo = getattr(Qt, grupo, None)
    if enum_grupo is not None and hasattr(enum_grupo, nombre):
        return getattr(enum_grupo, nombre)
    return getattr(Qt, nombre)


def dialog_accepted():
    dialog_code = getattr(QDialog, "DialogCode", None)
    if dialog_code is not None and hasattr(dialog_code, "Accepted"):
        return dialog_code.Accepted
    return QDialog.Accepted


def ejecutar_dialogo(dialogo):
    metodo_exec = getattr(dialogo, "exec", None)
    if metodo_exec is None:
        metodo_exec = getattr(dialogo, "exec_")
    return metodo_exec()


ALIGN_CENTER = qt_enum("AlignmentFlag", "AlignCenter")
ALIGN_LEFT = qt_enum("AlignmentFlag", "AlignLeft")
ALIGN_VCENTER = qt_enum("AlignmentFlag", "AlignVCenter")
KEEP_ASPECT_RATIO = qt_enum("AspectRatioMode", "KeepAspectRatio")
SMOOTH_TRANSFORMATION = qt_enum("TransformationMode", "SmoothTransformation")
APPLICATION_MODAL = qt_enum("WindowModality", "ApplicationModal")
WINDOW_DIALOG = qt_enum("WindowType", "Dialog")
WINDOW_CUSTOMIZE_HINT = qt_enum("WindowType", "CustomizeWindowHint")
WINDOW_TITLE_HINT = qt_enum("WindowType", "WindowTitleHint")


BASE = "https://infosipeb.planificacion.gob.bo"
API = f"{BASE}/api/geovisor/geo-sectors?children=true&internal=false"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://infosipeb.planificacion.gob.bo/geovisor",
    "Accept": "application/json, text/plain, */*",
}

CACHE_DIR = Path(QgsApplication.qgisSettingsDirPath()) / "cache_infosipeb"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def obtener_ruta_logo():
    return Path(__file__).parent / "logo.png"

def limpiar_nombre(texto, max_len=120):
    """Convierte un texto en nombre seguro para archivos/carpetas."""
    texto = str(texto or "sin_nombre").strip()
    texto = re.sub(r'[<>:"/\\|?*]', "_", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto[:max_len]

def mensaje(titulo, texto, icono="info"):
    """Muestra mensajes simples en QGIS."""
    if icono == "error":
        QMessageBox.critical(None, titulo, texto)
    elif icono == "warning":
        QMessageBox.warning(None, titulo, texto)
    else:
        QMessageBox.information(None, titulo, texto)


def obtener_catalogo():
    """Consulta el catálogo público y devuelve una lista plana de capas descargables."""
    resp = requests.get(API, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    capas = []

    for sector in data:
        sector_nombre = sector.get("titulo", "Sin sector")

        for categoria in sector.get("categorias", []):
            categoria_nombre = categoria.get("titulo", "Sin categoría")

            for recurso in categoria.get("cartographicResource", []):
                layer = recurso.get("layer")

                if not layer:
                    continue

                # Se cargan solamente las capas que tienen descarga externa habilitada.
                if recurso.get("enableExternalDownload") is not True:
                    continue

                url_descarga = f"{BASE}/api/upload/layers_download/download/descargar_{layer}.zip"

                capas.append({
                    "sector": sector_nombre,
                    "categoria": categoria_nombre,
                    "id": recurso.get("id"),
                    "nombre": recurso.get("name") or layer,
                    "layer": layer,
                    "formato": recurso.get("format"),
                    "geometria": recurso.get("typeGeom"),
                    "crs": recurso.get("crs"),
                    "bbox": recurso.get("bbox"),
                    "fecha_contenido": recurso.get("contentDate"),
                    "url_descarga": url_descarga,
                })

    return capas


class SelectorCapasInfoSipeb(QDialog):
    """Ventana única para elegir sector, categoría y mapa/capa."""

    def __init__(self, capas, parent=None):
        super().__init__(parent)
        self.capas = capas
        self.capa_seleccionada = None

        self.setWindowTitle("INFO-SIPEB - Cargar mapa")
        self.setMinimumWidth(630)
        self.resize(630, 360)
        self.setMinimumHeight(360)

        self.combo_sector = QComboBox()
        self.combo_categoria = QComboBox()
        self.txt_buscar = QLineEdit()
        self.combo_capa = QComboBox()
        self.btn_cargar = QPushButton("Cargar mapa")
        self.btn_cancelar = QPushButton("Cancelar")

        self._construir_interfaz()
        self._conectar_eventos()
        self._cargar_sectores()

    def _construir_interfaz(self):
        layout = QVBoxLayout(self)

        logo = QLabel()
        logo.setAlignment(ALIGN_CENTER)

        ruta_logo = obtener_ruta_logo()

        if ruta_logo.exists():
            pixmap = QPixmap(str(ruta_logo))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        390,
                        135,
                        KEEP_ASPECT_RATIO,
                        SMOOTH_TRANSFORMATION
                    )
                )
            else:
                logo.setText("INFO-SIPEB")
                logo.setStyleSheet("font-size: 15px; font-weight: bold;")
        else:
            logo.setText("INFO-SIPEB")
            logo.setStyleSheet("font-size: 15px; font-weight: bold;")

        layout.addWidget(logo)

        descripcion = QLabel(
            "Interconexión directa con el Geoportal oficial INFO-SIPEB para la consulta y descarga de mapas temáticos."
            "| https://infosipeb.planificacion.gob.bo/geovisor"
        )
        descripcion.setWordWrap(True)
        layout.addWidget(descripcion)

        form = QFormLayout()
        form.addRow("Sector:", self.combo_sector)
        form.addRow("Categoría:", self.combo_categoria)

        self.txt_buscar.setPlaceholderText("Buscar por nombre de mapa...")
        form.addRow("Buscar mapa:", self.txt_buscar)

        self.combo_capa.setMaxVisibleItems(18)
        form.addRow("Mapa / capa:", self.combo_capa)
        layout.addLayout(form)

        credito = QLabel(
            "Ing. MSc. Jorge Ayala Niño de Guzmàn | "
            "QGISBolivia.org"
        )
        credito.setWordWrap(True)
        credito.setAlignment(ALIGN_LEFT | ALIGN_VCENTER)
        credito.setStyleSheet(
            "font-size: 12px; color: #1F4E79; "
            "margin-top: 0px; margin-bottom: 0px;"
            "font-weight: bold"

        )

        botones = QHBoxLayout()
        botones.addWidget(credito, 1)
        botones.addWidget(self.btn_cancelar)
        botones.addWidget(self.btn_cargar)
        layout.addLayout(botones)

    def _conectar_eventos(self):
        self.combo_sector.currentIndexChanged.connect(self._actualizar_categorias)
        self.combo_categoria.currentIndexChanged.connect(self._actualizar_capas)
        self.txt_buscar.textChanged.connect(self._actualizar_capas)
        self.btn_cancelar.clicked.connect(self.reject)
        self.btn_cargar.clicked.connect(self._aceptar_seleccion)

    def _cargar_sectores(self):
        self.combo_sector.blockSignals(True)
        self.combo_sector.clear()

        sectores = sorted({c["sector"] for c in self.capas})
        self.combo_sector.addItems(sectores)

        self.combo_sector.blockSignals(False)
        self._actualizar_categorias()

    def _actualizar_categorias(self):
        sector = self.combo_sector.currentText()
        capas_sector = [c for c in self.capas if c["sector"] == sector]
        categorias = sorted({c["categoria"] for c in capas_sector})

        self.combo_categoria.blockSignals(True)
        self.combo_categoria.clear()
        self.combo_categoria.addItems(categorias)
        self.combo_categoria.blockSignals(False)

        self._actualizar_capas()

    def _actualizar_capas(self):
        sector = self.combo_sector.currentText()
        categoria = self.combo_categoria.currentText()
        busqueda = self.txt_buscar.text().strip().lower()

        capas_filtradas = [
            c for c in self.capas
            if c["sector"] == sector and c["categoria"] == categoria
        ]

        if busqueda:
            capas_filtradas = [
                c for c in capas_filtradas
                if busqueda in self._texto_busqueda(c)
            ]

        self.combo_capa.blockSignals(True)
        self.combo_capa.clear()

        for c in capas_filtradas:
            self.combo_capa.addItem(self._texto_combo(c), c)

        self.combo_capa.blockSignals(False)
        self.btn_cargar.setEnabled(bool(capas_filtradas))

    def _texto_busqueda(self, capa):
        return str(capa.get("nombre") or "").lower()

    def _texto_combo(self, capa):
        # En el selector se muestra únicamente el nombre del mapa.
        return capa.get("nombre") or "Sin nombre"

    def _aceptar_seleccion(self):
        capa = self.combo_capa.currentData()

        if not capa:
            QMessageBox.warning(
                self,
                "INFO-SIPEB",
                "Debe seleccionar un mapa/capa antes de continuar."
            )
            return

        self.capa_seleccionada = capa
        self.accept()


def elegir_capa(capas, iface=None):
    """Muestra una sola ventana para elegir sector, categoría y capa."""
    if not capas:
        mensaje("INFO-SIPEB", "No se encontraron capas con descarga externa habilitada.", "warning")
        return None

    parent = None
    if iface is not None:
        parent = None
        if iface is not None:
            try:
                parent = iface.mainWindow()
            except Exception:
                parent = None

    dialogo = SelectorCapasInfoSipeb(capas, parent)

    if ejecutar_dialogo(dialogo) == dialog_accepted():
        return dialogo.capa_seleccionada

    return None



class VentanaProcesoInfoSipeb(QDialog):
    """Ventana temporal sin botones para mostrar descarga y descompresión."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("INFO-SIPEB - Cargando mapa")
        self.setWindowModality(APPLICATION_MODAL)
        self.setWindowFlags(WINDOW_DIALOG | WINDOW_CUSTOMIZE_HINT | WINDOW_TITLE_HINT)
        self.setMinimumWidth(420)
        self.resize(420, 110)

        self.lbl_estado = QLabel("Preparando carga...")
        self.lbl_estado.setWordWrap(True)

        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setFormat("%p%")

        layout = QVBoxLayout(self)
        layout.addWidget(self.lbl_estado)
        layout.addWidget(self.barra)

    def actualizar(self, estado, porcentaje=None):
        self.lbl_estado.setText(estado)

        if porcentaje is None:
            self.barra.setRange(0, 0)
        else:
            self.barra.setRange(0, 100)
            self.barra.setValue(max(0, min(100, int(porcentaje))))

        QApplication.processEvents()


def descargar_zip(capa, progreso=None):
    """Descarga solo el ZIP de la capa elegida y muestra porcentaje de avance."""
    nombre_zip = limpiar_nombre(f"{capa['id']}_{capa['nombre']}") + ".zip"
    ruta_zip = CACHE_DIR / nombre_zip

    if ruta_zip.exists() and ruta_zip.stat().st_size > 0:
        if progreso:
            progreso.actualizar("Descarga: archivo encontrado en caché.", 100)
        return ruta_zip

    url = capa["url_descarga"]

    if progreso:
        progreso.actualizar("Descargando mapa...", 0)

    with requests.get(url, headers=HEADERS, stream=True, timeout=180) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"No se pudo descargar la capa. HTTP {resp.status_code}\nURL: {url}")

        tipo = resp.headers.get("content-type", "").lower()
        if "zip" not in tipo and "octet-stream" not in tipo:
            # Algunos servidores no devuelven bien el content-type.
            # No detenemos automáticamente, pero dejamos que zipfile valide después.
            pass

        total = int(resp.headers.get("content-length", 0) or 0)
        descargado = 0

        with open(ruta_zip, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue

                f.write(chunk)
                descargado += len(chunk)

                if progreso:
                    if total > 0:
                        porcentaje = int((descargado / total) * 100)
                        progreso.actualizar(f"Descargando mapa... {porcentaje}%", porcentaje)
                    else:
                        progreso.actualizar("Descargando mapa...", None)

    if progreso:
        progreso.actualizar("Descarga completada.", 100)

    return ruta_zip

def descomprimir_zip(ruta_zip, progreso=None):
    """Descomprime el ZIP en una carpeta de caché y muestra porcentaje de avance."""
    carpeta = CACHE_DIR / ruta_zip.stem
    carpeta.mkdir(parents=True, exist_ok=True)

    # Si ya fue descomprimido antes, se reutiliza.
    if any(carpeta.rglob("*")):
        if progreso:
            progreso.actualizar("Descompresión: carpeta encontrada en caché.", 100)
        return carpeta

    if not zipfile.is_zipfile(ruta_zip):
        raise RuntimeError(f"El archivo descargado no parece ser un ZIP válido:\n{ruta_zip}")

    if progreso:
        progreso.actualizar("Iniciando descompresión...", 0)

    with zipfile.ZipFile(ruta_zip, "r") as z:
        miembros = z.infolist()
        total = len(miembros)

        if total == 0:
            if progreso:
                progreso.actualizar("Descompresión completada.", 100)
            return carpeta

        for i, miembro in enumerate(miembros, start=1):
            z.extract(miembro, carpeta)
            if progreso:
                porcentaje = int((i / total) * 100)
                progreso.actualizar(f"Descomprimiendo archivos... {porcentaje}%", porcentaje)

    if progreso:
        progreso.actualizar("Descompresión completada.", 100)

    return carpeta



def tipo_geometria_memoria(origen):
    """Devuelve un tipo de geometría compatible con capas de memoria de QGIS."""
    try:
        tipo = QgsWkbTypes.displayString(origen.wkbType())
        if tipo and tipo.lower() not in {"unknown", "none", "nogeometry"}:
            return tipo
    except Exception:
        pass

    geom = origen.geometryType()
    if geom == QgsWkbTypes.PointGeometry:
        return "Point"
    if geom == QgsWkbTypes.LineGeometry:
        return "LineString"
    if geom == QgsWkbTypes.PolygonGeometry:
        return "Polygon"
    return "None"


def crear_capa_temporal(origen, nombre_capa):
    """Copia una capa vectorial de archivo a una capa temporal de memoria."""
    crs = origen.crs()
    authid = crs.authid() if crs and crs.isValid() else "EPSG:4326"
    tipo_geom = tipo_geometria_memoria(origen)
    uri = f"{tipo_geom}?crs={authid}"

    temporal = QgsVectorLayer(uri, nombre_capa, "memory")
    if not temporal.isValid():
        raise RuntimeError(f"No se pudo crear la capa temporal: {nombre_capa}")

    proveedor = temporal.dataProvider()
    proveedor.addAttributes(origen.fields())
    temporal.updateFields()

    lote = []
    for feat in origen.getFeatures():
        lote.append(feat)
        if len(lote) >= 1000:
            proveedor.addFeatures(lote)
            lote = []

    if lote:
        proveedor.addFeatures(lote)

    temporal.updateExtents()
    temporal.setCrs(crs)

    temporal.setCustomProperty("infosipeb_temporal", True)

    return temporal


def cargar_archivos_en_qgis(carpeta, capa, iface=None):
    """Carga archivos del ZIP directamente al panel de capas, sin crear grupos."""
    vector_ext = {".shp", ".gpkg", ".geojson", ".json", ".kml"}
    raster_ext = {".tif", ".tiff", ".asc"}

    archivos = list(carpeta.rglob("*"))

    candidatos_vector = [
        p for p in archivos
        if p.is_file() and p.suffix.lower() in vector_ext
    ]

    candidatos_raster = [
        p for p in archivos
        if p.is_file() and p.suffix.lower() in raster_ext
    ]

    cargadas = []

    # Los vectores se copian a capas temporales de memoria, sin activar edición.
    for p in candidatos_vector:
        nombre_capa = capa["nombre"] if len(candidatos_vector) == 1 else f"{capa['nombre']} - {p.stem}"
        origen = QgsVectorLayer(str(p), nombre_capa, "ogr")

        if origen.isValid():
            temporal = crear_capa_temporal(origen, nombre_capa)
            QgsProject.instance().addMapLayer(temporal, True)
            cargadas.append(temporal)

    # QGIS no maneja rásteres como capas temporales de memoria del mismo modo que vectores.
    # Si el ZIP trae ráster y no hay vector, se carga desde caché para no perder compatibilidad.
    if not cargadas:
        for p in candidatos_raster:
            nombre_capa = capa["nombre"] if len(candidatos_raster) == 1 else f"{capa['nombre']} - {p.stem}"
            lyr = QgsRasterLayer(str(p), nombre_capa)

            if lyr.isValid():
                QgsProject.instance().addMapLayer(lyr, True)
                cargadas.append(lyr)

    if not cargadas:
        extensiones = sorted({p.suffix.lower() for p in archivos if p.is_file()})
        raise RuntimeError(
            "No se pudo cargar ninguna capa compatible.\n\n"
            f"Carpeta: {carpeta}\n"
            f"Extensiones encontradas: {', '.join(extensiones) if extensiones else 'ninguna'}"
        )

    # Zoom a la primera capa cargada, si se está ejecutando desde QGIS.
    if iface is not None:
        try:
            iface.mapCanvas().setExtent(cargadas[0].extent())
            iface.mapCanvas().refresh()
        except Exception:
            pass

    return cargadas

def main(iface=None):
    progreso = None

    try:
        capas = obtener_catalogo()
        capa = elegir_capa(capas, iface)

        if capa is None:
            return

        try:
            parent = iface.mainWindow()
        except Exception:
            parent = None

        progreso = VentanaProcesoInfoSipeb(parent)
        progreso.show()
        progreso.actualizar("Preparando descarga...", 0)

        ruta_zip = descargar_zip(capa, progreso)
        carpeta = descomprimir_zip(ruta_zip, progreso)

        progreso.actualizar("Cargando mapa en QGIS...", 100)
        cargar_archivos_en_qgis(carpeta, capa, iface)

        # Al terminar correctamente, la ventana temporal desaparece y no se muestra mensaje final.
        progreso.close()
        progreso = None

    except Exception as e:
        if progreso is not None:
            progreso.close()
        mensaje("Error al cargar mapa INFO-SIPEB", str(e), "error")
