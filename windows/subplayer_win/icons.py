"""Line icons drawn for SubPlayer (24×24, stroke), tinted at run time — crisp at any screen scale."""
from __future__ import annotations

from functools import lru_cache

P = {
    "play": '<path d="M7 4.5v15l12.5-7.5z" fill="currentColor" stroke="none"/>',
    "pause": '<rect x="6" y="4.5" width="4" height="15" rx="1.2" fill="currentColor" stroke="none"/>'
             '<rect x="14" y="4.5" width="4" height="15" rx="1.2" fill="currentColor" stroke="none"/>',
    "folder": '<path d="M3 7.5a2 2 0 0 1 2-2h4l2 2.2h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "link": '<path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2"/>'
            '<path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "captions": '<rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M10.5 10.3a2.3 2.3 0 1 0 0 3.4M17.5 10.3a2.3 2.3 0 1 0 0 3.4"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    "film": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
    "star": '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
    "star_fill": '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" fill="currentColor"/>',
    "cards": '<rect x="7" y="3.5" width="13" height="16" rx="2.5"/><path d="M4 7v11a2.5 2.5 0 0 0 2.5 2.5H15"/><path d="M11 9.5h5M11 13h3"/>',
    "puzzle": '<path d="M9 4h3.5a1.8 1.8 0 1 1 3.5 0H19v4a1.8 1.8 0 1 1 0 3.5V15h-3.5a1.8 1.8 0 1 0-3.5 0H8.5v-3.5a1.8 1.8 0 1 1 0-3.5V4z"/>'
              '<path d="M5 15v5h5"/>',
    "sync": '<path d="M20 11a8 8 0 0 0-14.3-4.6L4 8.5"/><path d="M4 4v4.5h4.5"/><path d="M4 13a8 8 0 0 0 14.3 4.6L20 15.5"/><path d="M20 20v-4.5h-4.5"/>',
    "gear": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.6M12 18.6v2.6M21.2 12h-2.6M5.4 12H2.8M18.5 5.5l-1.8 1.8M7.3 16.7l-1.8 1.8M18.5 18.5l-1.8-1.8M7.3 7.3L5.5 5.5"/>'
            '<circle cx="12" cy="12" r="6.6"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.3a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.5v.6"/><circle cx="12" cy="17" r=".6" fill="currentColor"/>',
    "back5": '<path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.7"/><path d="M4 4v4.7h4.7"/><text x="12" y="15.4" font-size="7.5" text-anchor="middle" '
             'fill="currentColor" stroke="none" font-family="Segoe UI, Arial" font-weight="700">5</text>',
    "fwd5": '<path d="M20 12a8 8 0 1 1-2.4-5.7L20 8.7"/><path d="M20 4v4.7h-4.7"/><text x="12" y="15.4" font-size="7.5" text-anchor="middle" '
            'fill="currentColor" stroke="none" font-family="Segoe UI, Arial" font-weight="700">5</text>',
    "prev": '<path d="M18 5.5v13L9 12z" fill="currentColor" stroke="none"/><rect x="5.5" y="5.5" width="2.4" height="13" rx="1" fill="currentColor" stroke="none"/>',
    "next": '<path d="M6 5.5v13l9-6.5z" fill="currentColor" stroke="none"/><rect x="16.1" y="5.5" width="2.4" height="13" rx="1" fill="currentColor" stroke="none"/>',
    "repeat": '<path d="M4 11V9a3 3 0 0 1 3-3h12"/><path d="M16 3l3 3-3 3"/><path d="M20 13v2a3 3 0 0 1-3 3H5"/><path d="M8 21l-3-3 3-3"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/>',
    "scissors": '<circle cx="6.5" cy="6.5" r="2.7"/><circle cx="6.5" cy="17.5" r="2.7"/><path d="M8.6 8.4L20 18M8.6 15.6L20 6"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "volume": '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
    "translate": '<path d="M3.5 6h9M8 4v2M10.5 6c-.6 3.5-3 6.6-6.5 8M6 9c1.1 2.1 2.9 3.8 5 4.8"/><path d="M13 20l4-9 4 9M14.4 17h5.2"/>',
    "sparkles": '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.8 2.2 2.2.8-2.2.8L19 21l-.8-2.2-2.2-.8 2.2-.8z"/>',
    "chev": '<path d="M7 10l5 5 5-5"/>',
    "trash": '<path d="M4.5 6.5h15M9.5 6.5V4.5h5v2M6.5 6.5l1 13h9l1-13M10.2 10.5v6M13.8 10.5v6"/>',
    "bell": '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
    "download": '<path d="M12 4v11M7.5 10.5L12 15l4.5-4.5"/><path d="M4.5 17.5v1.5a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-1.5"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "book": '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/>',
    "panel": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M14.5 4v16"/>',
    "fullscreen": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "send": '<path d="M21 3L10 14"/><path d="M21 3l-7 18-4-7-7-4z"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l2 2M15 8l2 2"/>',
    "drop": '<path d="M12 3v12M7 10l5 5 5-5"/><rect x="3" y="17" width="18" height="4" rx="2"/>',
    "flame": '<path d="M12 21a6.5 6.5 0 0 0 6.5-6.5c0-3.7-2.6-6.1-4.1-9.5-.6 2.5-2 3.8-3.4 4.6C9.7 8 9.6 6.4 9.9 4.8 7 6.9 5.5 10.6 5.5 14.5A6.5 6.5 0 0 0 12 21z"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20.5 20.5"/>',
    "compass": '<circle cx="12" cy="12" r="9"/><path d="M15.8 8.2l-2.3 5.3-5.3 2.3 2.3-5.3z" fill="currentColor"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M4 4l16 16"/><path d="M9.9 5.8A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3 3.7M6.4 7.4A16.5 16.5 0 0 0 2.5 12S6 18.5 12 18.5a9.3 9.3 0 0 0 4.2-1"/>',
    "textsize": '<path d="M3.5 18.5L8 6.5l4.5 12M5.2 14h5.6"/><path d="M14 18.5l3.3-8 3.2 8M15.1 15.8h4.4"/>',
    "list": '<path d="M9 6.5h11M9 12h11M9 17.5h11"/><circle cx="4.8" cy="6.5" r="1.1" fill="currentColor"/><circle cx="4.8" cy="12" r="1.1" fill="currentColor"/><circle cx="4.8" cy="17.5" r="1.1" fill="currentColor"/>',
    "mute": '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.6 2.5 3.9 5.5 3.9 9s-1.3 6.5-3.9 9c-2.6-2.5-3.9-5.5-3.9-9S9.4 5.5 12 3z"/>',
    "bars": '<path d="M5 19.5v-5M10 19.5v-9M15 19.5V7M20 19.5V4"/>',
    "edit": '<path d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "export": '<path d="M12 15V3.5M7.5 8L12 3.5 16.5 8"/><path d="M5 13v5.5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V13"/>',
    "where": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/><path d="M8.5 11h5M11 8.5v5"/>',
    "copy": '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M5.5 15.5h-1a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
    "paste": '<path d="M9 4.5H6.5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-12a2 2 0 0 0-2-2H15"/><rect x="9" y="3" width="6" height="3.5" rx="1"/><path d="M8.5 12h7M8.5 16h5"/>',
    "palette": '<path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.2 0 1.8-.9 1.8-1.8 0-1-.9-1.4-.9-2.4 0-.9.8-1.6 1.7-1.6h2.1a3.8 3.8 0 0 0 3.8-3.8C20.5 6.8 16.7 3.5 12 3.5z"/><circle cx="7.8" cy="11" r="1"/><circle cx="10.5" cy="7.5" r="1"/><circle cx="15" cy="7.8" r="1"/>',
    "notes": '<path d="M6 3h10l3 3v15H6z"/><path d="M9 9h7M9 13h7M9 17h4"/>',
    "paraphrase": '<path d="M4 7h11"/><path d="M12 4l3 3-3 3"/><path d="M20 17H9"/><path d="M12 14l-3 3 3 3"/><path d="M4 17h1M19 7h1"/>',
    "pen": '<path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 6l3 3"/>',
    "study": '<path d="M3 8.5L12 4l9 4.5-9 4.5z"/><path d="M7 10.5v4.5c0 1.4 2.2 3 5 3s5-1.6 5-3v-4.5"/><path d="M21 8.5v6"/>',
}


def svg(name: str, color: str, stroke: float = 1.8) -> bytes:
    body = P.get(name, P["help"]).replace("currentColor", color)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>').encode()


@lru_cache(maxsize=512)
def pixmap(name: str, color: str = "#EDEBF5", size: int = 20, stroke: float = 1.8):
    from PySide6.QtCore import QByteArray, QRectF, Qt
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    r = QSvgRenderer(QByteArray(svg(name, color, stroke)))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p, QRectF(0, 0, size * scale, size * scale))
    p.end()
    pm.setDevicePixelRatio(scale)
    return pm


def icon(name: str, color: str = "#EDEBF5", size: int = 20, active: str | None = None):
    """QIcon with an optional brighter version for the checked / hover state."""
    from PySide6.QtGui import QIcon
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Normal, QIcon.Off)
    if active:
        ic.addPixmap(pixmap(name, active, size), QIcon.Normal, QIcon.On)
        ic.addPixmap(pixmap(name, active, size), QIcon.Active, QIcon.Off)
    ic.addPixmap(pixmap(name, "#55526f", size), QIcon.Disabled, QIcon.Off)
    return ic


def app_icon():
    """The planet-and-ring logo used for the window and the tray."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap, QRadialGradient
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(s, s)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        g = QRadialGradient(QPointF(s * 0.38, s * 0.32), s * 0.55)
        g.setColorAt(0, QColor("#B4FBFF"))
        g.setColorAt(0.45, QColor("#8B5CFF"))
        g.setColorAt(1, QColor("#3A137A"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6))
        pen = QPen(QColor("#FF4FD8"), max(1.0, s * 0.06))
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.save()
        p.translate(s / 2, s / 2)
        p.rotate(-18)
        p.drawEllipse(QRectF(-s * 0.47, -s * 0.13, s * 0.94, s * 0.26))
        p.restore()
        p.end()
        ic.addPixmap(pm)
    return ic
