"""SubPlayer "Nebula" look: deep-space background, glass panels, neon glow (matches the phone app's colours)."""
from __future__ import annotations

import sys
from pathlib import Path

CYAN = "#3EF0FF"
MAGENTA = "#FF4FD8"
GOLD = "#FFD166"
VIOLET = "#8B5CFF"
MINT = "#5BE38F"
BG = "#05040D"
CARD = "#141228"
LIGHT = "#EDEBF5"
DIM = "#9A98B5"
ARTICLE = {"der": "#5AA9FF", "die": "#FF6B9A", "das": "#5BE38F"}

UI_FONT = "'Segoe UI Variable Text', 'Segoe UI', 'Inter', 'Vazirmatn', sans-serif"
FA_FONT = "Vazirmatn"           # bundled (SIL Open Font License) — clean Persian on every PC

GLASS = "rgba(20, 17, 44, 0.62)"
GLASS_BORDER = "rgba(160, 140, 255, 0.22)"

_QSS_DEFAULT = f"""
* {{ font-family: {UI_FONT}; font-size: 10.5pt; color: {LIGHT}; }}
QMainWindow, QDialog {{ background: {BG}; }}
QDialog {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0B0920, stop:0.6 #120C2C, stop:1 #071226); }}
QWidget#page, QWidget#clear, QStackedWidget, QScrollArea > QWidget > QWidget#page {{ background: transparent; }}

/* ---------- glass surfaces ---------- */
QFrame#rail {{ background: rgba(12, 10, 30, 0.72); border: none; border-right: 1px solid {GLASS_BORDER}; }}
QFrame#topbar {{ background: transparent; }}
QFrame#panel {{ background: {GLASS}; border: 1px solid {GLASS_BORDER}; border-radius: 22px; }}
QFrame#card {{ background: {GLASS}; border: 1px solid {GLASS_BORDER}; border-radius: 22px; }}
QFrame#hero {{ background: rgba(18, 14, 42, 0.55); border: 1px solid rgba(62, 240, 255, 0.18); border-radius: 30px; }}
QFrame#videoFrame {{ background: black; border: 1px solid rgba(62, 240, 255, 0.30); border-radius: 18px; }}
QFrame#subs {{ background: rgba(6, 5, 18, 0.72); border: 1px solid rgba(139, 92, 255, 0.35); border-radius: 18px; }}
QFrame#controls {{ background: rgba(14, 12, 34, 0.70); border: 1px solid {GLASS_BORDER}; border-radius: 20px; }}
QFrame#recent {{ background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.10); border-radius: 16px; }}
QFrame#recent:hover {{ border: 1px solid {CYAN}; background: rgba(62,240,255,0.07); }}
QFrame#sep {{ background: rgba(160,140,255,0.18); max-height: 1px; min-height: 1px; border: none; }}

/* ---------- text ---------- */
QLabel {{ background: transparent; }}
QLabel#hint {{ color: {DIM}; }}
QLabel#small {{ color: {DIM}; font-size: 9pt; }}
QLabel#time {{ color: {DIM}; font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 10pt; }}
QLabel#badge {{ background: rgba(255, 209, 102, 0.12); border: 1px solid rgba(255, 209, 102, 0.45); color: {GOLD};
    border-radius: 10px; padding: 3px 9px; font-weight: 700; font-size: 9pt; }}
QLabel#ab {{ color: {CYAN}; font-weight: 600; }}
QLabel#railName {{ color: {DIM}; font-size: 8.5pt; }}

/* ---------- buttons ---------- */
QPushButton {{ background: rgba(255,255,255,0.055); border: 1px solid rgba(255,255,255,0.13); border-radius: 13px;
    padding: 7px 15px; font-weight: 500; }}
QPushButton:hover {{ border: 1px solid {CYAN}; background: rgba(62,240,255,0.09); }}
QPushButton:pressed {{ background: rgba(62,240,255,0.18); }}
QPushButton:checked {{ border: 1px solid {CYAN}; background: rgba(62,240,255,0.16); color: white; }}
QPushButton[accent="true"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {VIOLET}, stop:1 {MAGENTA}); border: none;
    color: white; font-weight: 700; }}
QPushButton[accent="true"]:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #9D74FF, stop:1 #FF6BE0); }}
QPushButton:disabled {{ color: #5d5a78; border-color: #2a2745; background: rgba(255,255,255,0.02); }}
QPushButton[kind="icon"] {{ background: transparent; border: 1px solid transparent; border-radius: 14px; padding: 7px; }}
QPushButton[kind="icon"]:hover {{ background: rgba(255,255,255,0.07); border: 1px solid rgba(62,240,255,0.45); }}
QPushButton[kind="icon"]:checked {{ background: rgba(62,240,255,0.16); border: 1px solid {CYAN}; }}
QPushButton[kind="play"] {{ border: none; border-radius: 29px; min-width: 58px; max-width: 58px; min-height: 58px; max-height: 58px;
    padding: 0; background: qradialgradient(cx:0.35, cy:0.3, radius:0.9, fx:0.35, fy:0.3, stop:0 #7CF6FF, stop:0.55 {VIOLET}, stop:1 #5A2BD8); }}
QPushButton[kind="play"]:hover {{ background: qradialgradient(cx:0.35, cy:0.3, radius:0.9, fx:0.35, fy:0.3, stop:0 #B4FBFF, stop:0.55 #9D74FF, stop:1 #6A3BE8); }}
QToolButton[kind="nav"] {{ background: transparent; border: 1px solid transparent; border-radius: 16px; padding: 9px 4px 7px 4px;
    color: {DIM}; font-size: 8.5pt; font-weight: 600; }}
QToolButton[kind="nav"]:hover {{ background: rgba(255,255,255,0.06); color: {LIGHT}; }}
QToolButton[kind="nav"]:checked {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(139,92,255,0.38), stop:1 rgba(255,79,216,0.22));
    border: 1px solid rgba(62,240,255,0.55); color: white; }}
QPushButton[kind="chip"] {{ border-radius: 12px; padding: 6px 12px; font-size: 9.5pt; }}
QPushButton[kind="link"] {{ background: transparent; border: none; color: {CYAN}; padding: 2px 4px; text-align: left; }}
QPushButton[kind="link"]:hover {{ color: white; text-decoration: underline; }}

QToolButton {{ background: transparent; border: none; }}

/* ---------- inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{ background: rgba(255,255,255,0.055); border: 1px solid rgba(255,255,255,0.14);
    border-radius: 12px; padding: 7px 9px; selection-background-color: {VIOLET}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {CYAN}; background: rgba(62,240,255,0.05); }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: #120F2A; border: 1px solid {GLASS_BORDER}; border-radius: 10px; padding: 4px;
    selection-background-color: rgba(139,92,255,0.45); outline: none; }}
QRadioButton, QCheckBox {{ spacing: 9px; background: transparent; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid rgba(255,255,255,0.35); background: rgba(255,255,255,0.05); }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator {{ border-radius: 5px; }}
QRadioButton::indicator:checked, QCheckBox::indicator:checked {{ background: qradialgradient(cx:0.5,cy:0.5,radius:0.6, stop:0 {CYAN}, stop:0.55 {VIOLET}, stop:0.6 rgba(0,0,0,0));
    border: 1px solid {CYAN}; }}
QCheckBox::indicator:checked {{ background: {VIOLET}; }}

/* ---------- lists, text views ---------- */
QTextBrowser {{ background: transparent; border: none; }}
QTableWidget {{ background: rgba(255,255,255,0.025); alternate-background-color: rgba(255,255,255,0.045); color: {LIGHT};
    border: 1px solid rgba(255,255,255,0.07); border-radius: 12px; gridline-color: transparent; outline: none; }}
QTableWidget::item {{ padding: 4px 8px; border: none; }}
QTableWidget::item:selected {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(139,92,255,0.45), stop:1 rgba(62,240,255,0.12)); color: #FFFFFF; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: #141228; color: {DIM}; border: none; border-bottom: 1px solid rgba(255,255,255,0.08);
    padding: 6px 8px; font-weight: 600; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QListWidget {{ background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.07); border-radius: 16px; padding: 4px; outline: none; }}
QListWidget::item {{ padding: 10px 10px; border-radius: 12px; margin: 2px; }}
QListWidget::item:hover {{ background: rgba(255,255,255,0.05); }}
QListWidget::item:selected {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(139,92,255,0.45), stop:1 rgba(62,240,255,0.12));
    color: white; }}

/* ---------- menus & tips (no more white pop-ups) ---------- */
QMenu {{ background: #110E28; border: 1px solid rgba(139,92,255,0.45); border-radius: 14px; padding: 6px; }}
QMenu::item {{ padding: 8px 22px 8px 14px; border-radius: 9px; color: {LIGHT}; background: transparent; }}
QMenu::item:selected {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(139,92,255,0.55), stop:1 rgba(255,79,216,0.30)); color: white; }}
QMenu::item:disabled {{ color: #6f6c8c; }}
QMenu::separator {{ height: 1px; background: rgba(160,140,255,0.2); margin: 5px 8px; }}
QToolTip {{ background: #141130; color: {LIGHT}; border: 1px solid {VIOLET}; border-radius: 8px; padding: 6px 8px; }}

/* ---------- slider / progress ---------- */
QSlider::groove:horizontal {{ height: 6px; background: rgba(255,255,255,0.10); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {CYAN}, stop:0.6 {VIOLET}, stop:1 {MAGENTA}); border-radius: 3px; }}
QSlider::handle:horizontal {{ background: qradialgradient(cx:0.5,cy:0.5,radius:0.5, stop:0 white, stop:0.6 #E6FEFF, stop:1 {CYAN});
    width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QProgressBar {{ background: rgba(255,255,255,0.08); border: none; border-radius: 6px; text-align: center; height: 12px; font-size: 8pt; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {CYAN}, stop:1 {MAGENTA}); border-radius: 6px; }}

/* ---------- scroll bars ---------- */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(160,140,255,0.30); border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {VIOLET}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: rgba(160,140,255,0.30); border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QStatusBar {{ background: rgba(8, 7, 20, 0.88); color: {DIM}; border-top: 1px solid rgba(160,140,255,0.12); }}
QStatusBar::item {{ border: none; }}
QMessageBox, QInputDialog {{ background: #0E0B24; }}
QMessageBox QLabel {{ color: {LIGHT}; }}
"""


# ====================================================================== themes
# A theme = three accent colours (highlights / buttons from → to) and the tint of the dark surfaces. Every colour of the
# default "Nebula" look — in this style sheet, in the space background and in the widgets — is re-coloured through shade():
# cyan-ish colours follow the theme's first accent, violet-ish the second, magenta-ish the third, dark and greyish
# colours take the theme's tint. Level colours (A1…C2), der/die/das and the gold of saved words stay as they are.
import colorsys
import re as _re

THEMES = {   # key: (name, accent 1, accent 2, accent 3, tint hue °, tint strength, darkness)
    "nebula":   ("Nebula — violet night (standard)", "#3EF0FF", "#8B5CFF", "#FF4FD8", 250, 1.00, 1.00),
    "ocean":    ("Ocean — deep blue",                "#6CCBFF", "#2F7BFF", "#6A5CFF", 218, 1.00, 1.00),
    "aurora":   ("Aurora — green and teal",          "#4DFFC0", "#12B5A0", "#2E86E0", 172, 0.90, 1.00),
    "forest":   ("Forest — moss and lime",           "#B8F06A", "#2FA35F", "#1FA890", 135, 0.70, 1.00),
    "sunset":   ("Sunset — amber and coral",         "#FFB86B", "#FF6A4D", "#E8408A", 345, 0.80, 1.00),
    "rose":     ("Rose — pink and plum",             "#FF9BD0", "#B45CFF", "#FF4F8B", 312, 0.80, 1.00),
    "graphite": ("Graphite — calm grey",             "#A9C7FF", "#5B6E94", "#7C8FBF", 220, 0.22, 1.00),
    "midnight": ("Midnight — pure black",            "#3EF0FF", "#8B5CFF", "#FF4FD8", 250, 0.55, 0.35),
}
_DEFAULTS = dict(CYAN=CYAN, MAGENTA=MAGENTA, VIOLET=VIOLET, BG=BG, CARD=CARD, LIGHT=LIGHT, DIM=DIM)
_current = {"key": "nebula", "accent": ""}
_fam: list = []          # [(default hue, default l, default s, target h, target l, target s)] for cyan / violet / magenta
_tint = (250.0, 1.0, 1.0)


def _hls(hexc: str):
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, l, s


def _hex(h: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, min(1.0, max(0.0, l)), min(1.0, max(0.0, s)))
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def _rgb(r: int, g: int, b: int) -> tuple[int, int, int]:
    """One colour of the default look in the current theme."""
    if _current["key"] == "nebula" and not _current["accent"]:
        return r, g, b
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    h *= 360
    if l < 0.02 or l > 0.985 or s < 0.08:
        return r, g, b                                              # black, white, pure greys
    th, ts, tl = _tint
    if l < 0.24 or s < 0.42:                                        # dark surfaces and greyish text: the theme's tint
        out = _hex(th + (h - 250) * 0.3, l * (tl if l < 0.24 else 1.0), s * ts)
    else:
        best = min(_fam, key=lambda f: abs((h - f[0] + 180) % 360 - 180))
        if abs((h - best[0] + 180) % 360 - 180) > 36:
            return r, g, b                                          # gold, green, orange, red … keep their meaning
        dh, dl, ds, t_h, t_l, t_s = best
        out = _hex(t_h + (h - dh), l if l > 0.85 else l * (t_l / dl), s * (t_s / ds))
    return int(out[1:3], 16), int(out[3:5], 16), int(out[5:7], 16)


def shade(color: str) -> str:
    """A "#RRGGBB" colour of the default look → the same role in the current theme."""
    if not (isinstance(color, str) and len(color) == 7 and color[0] == "#"):
        return color
    try:
        return "#%02X%02X%02X" % _rgb(int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
    except ValueError:
        return color


c = shade


def recolor(text: str) -> str:
    """Every #RRGGBB and rgb()/rgba() colour in a style sheet or HTML snippet → current theme."""
    text = _re.sub(r"#[0-9A-Fa-f]{6}\b", lambda m: shade(m.group(0)), text)
    return _re.sub(r"(rgba?\(\s*)(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})",
                   lambda m: m.group(1) + "%d, %d, %d" % _rgb(int(m.group(2)), int(m.group(3)), int(m.group(4))), text)


def accents_from(color: str) -> tuple[str, str, str]:
    """Three accents from one colour of your choice (its two neighbours on the colour wheel join it)."""
    h, l, s = _hls(color)
    s = max(0.6, s)
    return _hex(h, max(0.58, min(0.75, l)), s), _hex(h - 28, 0.52, s * 0.9), _hex(h + 28, 0.56, s)


def apply(key: str = "nebula", accent: str = "") -> None:
    """Chooses the theme (and optionally your own accent colour). Call before the window is built."""
    global CYAN, MAGENTA, VIOLET, BG, CARD, LIGHT, DIM, GLASS, GLASS_BORDER, QSS, _tint
    if key not in THEMES:
        key = "nebula"
    if not (isinstance(accent, str) and _re.fullmatch(r"#[0-9A-Fa-f]{6}", accent or "")):
        accent = ""
    _, a1, a2, a3, th, ts, tl = THEMES[key]
    if accent:
        a1, a2, a3 = accents_from(accent)
    _current.update(key=key, accent=accent)
    _tint = (float(th), ts, tl)
    _fam[:] = [(*_hls(d), *_hls(t)) for d, t in ((_DEFAULTS["CYAN"], a1), (_DEFAULTS["VIOLET"], a2), (_DEFAULTS["MAGENTA"], a3))]
    CYAN, VIOLET, MAGENTA = a1, a2, a3
    BG, CARD, LIGHT, DIM = (shade(_DEFAULTS[k]) for k in ("BG", "CARD", "LIGHT", "DIM"))
    GLASS = recolor("rgba(20, 17, 44, 0.62)")
    GLASS_BORDER = recolor("rgba(160, 140, 255, 0.22)")
    QSS = recolor(_QSS_DEFAULT)


def current() -> tuple[str, str]:
    return _current["key"], _current["accent"]


apply()


def fa_span(text: str, size: str = "14pt", color: str = "") -> str:
    """Right-to-left Persian block in the bundled font."""
    c = f"color:{color};" if color else ""
    return f"<div dir='rtl' style='font-family:{FA_FONT};font-size:{size};{c}'>{text}</div>"


def load_fonts() -> list[str]:
    """Registers the bundled fonts with Qt (call after QApplication exists)."""
    from PySide6.QtGui import QFontDatabase
    out = []
    folder = Path(__file__).resolve().parent / "fonts"
    for f in sorted(folder.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(f))
        if fid >= 0:
            out += QFontDatabase.applicationFontFamilies(fid)
    return out


def glow(widget, color: str | None = None, blur: int = 38, alpha: int = 150, dy: int = 0):
    """Soft neon halo around a widget."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    eff = QGraphicsDropShadowEffect(widget)
    col = QColor(color or VIOLET)
    col.setAlpha(alpha)
    eff.setColor(col)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    widget.setGraphicsEffect(eff)
    return eff


def repolish(*widgets):
    for w in widgets:
        w.style().unpolish(w)
        w.style().polish(w)


def dark_title_bar(window):
    """Windows 10/11: dark window frame in the app's own night colour (no-op elsewhere)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        for attr in (20, 19):                                        # DWMWA_USE_IMMERSIVE_DARK_MODE (new / old builds)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), 4) == 0:
                break
        def colorref(hexc):                                           # COLORREF is 0x00BBGGRR
            return ctypes.c_int(int(hexc[5:7] + hexc[3:5] + hexc[1:3], 16))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref(shade("#0B0A20"))), 4)   # DWMWA_CAPTION_COLOR (Windows 11)
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(colorref(VIOLET)), 4)             # DWMWA_BORDER_COLOR
    except Exception:
        pass
