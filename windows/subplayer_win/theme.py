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

QSS = f"""
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


def glow(widget, color: str = VIOLET, blur: int = 38, alpha: int = 150, dy: int = 0):
    """Soft neon halo around a widget."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    eff = QGraphicsDropShadowEffect(widget)
    c = QColor(color)
    c.setAlpha(alpha)
    eff.setColor(c)
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
        caption = ctypes.c_int(0x00200A0B)                            # COLORREF 0x00BBGGRR → #0B0A20
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), 4)  # DWMWA_CAPTION_COLOR (Windows 11)
        border = ctypes.c_int(0x00FF5C8B)                             # violet frame line
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border), 4)   # DWMWA_BORDER_COLOR
    except Exception:
        pass
