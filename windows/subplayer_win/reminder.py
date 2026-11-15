"""
Daily review reminder, like the phone's notification: a Windows scheduled task starts
"SubPlayer.exe --remind" at the chosen hour; it shows a notification only when words are due, then quits.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TASK = "SubPlayer daily review"


def launch_command() -> str:
    """The command the scheduled task runs (packaged .exe, or pythonw + run.py from source)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --remind'
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    run = Path(__file__).resolve().parent.parent / "run.py"
    return f'"{pyw if pyw.exists() else py}" "{run}" --remind'


def create_args(hour: int) -> list[str]:
    hour = max(0, min(23, int(hour)))
    return ["schtasks", "/Create", "/F", "/SC", "DAILY", "/TN", TASK, "/TR", launch_command(), "/ST", f"{hour:02d}:00"]


def delete_args() -> list[str]:
    return ["schtasks", "/Delete", "/F", "/TN", TASK]


def set_reminder(on: bool, hour: int) -> str:
    """Returns a short status message; raises on failure."""
    if os.name != "nt":
        raise RuntimeError("Daily reminders use Windows' Task Scheduler — available in the Windows build")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if on:
        r = subprocess.run(create_args(hour), capture_output=True, text=True, creationflags=flags)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout or "schtasks failed").strip())
        return f"Daily reminder set for {hour:02d}:00 — you'll get a notification when words are due"
    r = subprocess.run(delete_args(), capture_output=True, text=True, creationflags=flags)
    return "Daily reminder off"


def remind_main() -> int:
    """Entry for --remind: notification if words are due, then exit."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    from . import icons
    from .store import WordStore, now_ms
    try:
        due = len(WordStore().due(now_ms()))
    except Exception:
        due = 0
    if due <= 0:
        return 0
    app = QApplication(sys.argv[:1])
    tray = QSystemTrayIcon(icons.app_icon())
    tray.setToolTip("SubPlayer")
    tray.show()

    def open_app():
        cmd = launch_command().replace(" --remind", "")
        subprocess.Popen(cmd, shell=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        app.quit()

    tray.messageClicked.connect(open_app)
    tray.activated.connect(lambda *_: open_app())
    tray.showMessage("SubPlayer", f"{due} word{'s' if due != 1 else ''} waiting for review — a few minutes keeps your streak 🔥",
                     icons.app_icon(), 15000)
    QTimer.singleShot(20000, app.quit)
    return app.exec()
