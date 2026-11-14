"""Dark neon look (matches the phone app)."""

CYAN = "#3EF0FF"
MAGENTA = "#FF4FD8"
GOLD = "#FFD166"
VIOLET = "#8B5CFF"
BG = "#0A0A14"
CARD = "#141428"
LIGHT = "#EDEBF5"
DIM = "#9A98B5"
ARTICLE = {"der": "#5AA9FF", "die": "#FF6B9A", "das": "#5BE38F"}

QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 10.5pt; color: {LIGHT}; }}
QMainWindow, QDialog, QWidget#page {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0A0A14, stop:0.55 #120F2A, stop:1 #0B1424); }}
QToolBar {{ background: rgba(20,20,40,0.85); border: none; padding: 4px; spacing: 4px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 10px; padding: 6px 10px; }}
QToolButton:hover {{ border: 1px solid {CYAN}; background: rgba(62,240,255,0.08); }}
QToolButton:checked {{ border: 1px solid {MAGENTA}; background: rgba(255,79,216,0.15); }}
QPushButton {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.14); border-radius: 14px; padding: 6px 14px; }}
QPushButton:hover {{ border: 1px solid {CYAN}; }}
QPushButton:checked, QPushButton[accent="true"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {VIOLET}, stop:1 {MAGENTA}); border: none; color: white; font-weight: 600; }}
QPushButton:disabled {{ color: #666; border-color: #333; }}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15);
    border-radius: 10px; padding: 6px; selection-background-color: {VIOLET}; }}
QLineEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {CYAN}; }}
QComboBox QAbstractItemView {{ background: {CARD}; }}
QTextBrowser {{ background: transparent; border: none; }}
QListWidget {{ background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; }}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
QListWidget::item:selected {{ background: rgba(139,92,255,0.30); }}
QSlider::groove:horizontal {{ height: 6px; background: rgba(255,255,255,0.12); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {CYAN}, stop:1 {MAGENTA}); border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; width: 14px; margin: -5px 0; border-radius: 7px; }}
QProgressBar {{ background: rgba(255,255,255,0.08); border: none; border-radius: 6px; text-align: center; height: 14px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {CYAN}, stop:1 {MAGENTA}); border-radius: 6px; }}
QDockWidget {{ titlebar-close-icon: none; }}
QDockWidget::title {{ background: rgba(20,20,40,0.9); padding: 6px; }}
QStatusBar {{ background: rgba(10,10,20,0.9); color: {DIM}; }}
QLabel#title {{ font-size: 18pt; font-weight: 800; color: {CYAN}; }}
QLabel#hint {{ color: {DIM}; }}
QFrame#card {{ background: rgba(20,20,40,0.75); border: 1px solid rgba(139,92,255,0.35); border-radius: 18px; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: {CARD}; color: {LIGHT}; border: 1px solid {VIOLET}; }}
"""
