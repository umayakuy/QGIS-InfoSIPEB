def classFactory(iface):
    from .plugin import InfoSIPEB
    return InfoSIPEB(iface)
