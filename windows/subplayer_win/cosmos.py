"""The living backdrop: deep space, drifting nebula, an aurora ribbon and twinkling stars; plus the hero planet and
gradient titles. Everything heavy is pre-rendered once per window size, so each frame only blits a few pictures."""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class Cosmos(QWidget):
    FPS = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self._t0 = time.monotonic()
        self._layers = None
        self._size = None
        self.rnd = random.Random(7)
        self.twinkles = []
        self.timer = QTimer(self, interval=1000 // self.FPS, timeout=self.update)
        self.motion = True

    # animation on/off (the window turns it off while a video plays, when minimised, or in Settings)
    def set_running(self, on: bool):
        on = on and self.motion
        if on and not self.timer.isActive():
            self.timer.start()
        elif not on and self.timer.isActive():
            self.timer.stop()
            self.update()

    def _build(self):
        w, h = max(self.width(), 2), max(self.height(), 2)
        self._size = (w, h)
        # 1. sky + fixed stars
        sky = QPixmap(w, h)
        p = QPainter(sky)
        g = QLinearGradient(0, 0, w * 0.3, h)
        g.setColorAt(0, QColor("#05040D"))
        g.setColorAt(0.5, QColor("#0B0820"))
        g.setColorAt(1, QColor("#050B1A"))
        p.fillRect(0, 0, w, h, g)
        p.setRenderHint(QPainter.Antialiasing)
        n = int(w * h / 4200)
        for _ in range(n):
            x, y = self.rnd.random() * w, self.rnd.random() * h
            r = self.rnd.choice((0.5, 0.6, 0.7, 0.9, 1.1, 1.4))
            c = QColor(self.rnd.choice(("#FFFFFF", "#CFE9FF", "#E9D9FF", "#FFE9F7")))
            c.setAlpha(self.rnd.randint(60, 200))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(x, y), r, r)
        p.end()
        # 2. nebula (bigger than the window so it can drift)
        neb = QPixmap(int(w * 1.2), int(h * 1.2))
        neb.fill(Qt.transparent)
        p = QPainter(neb)
        p.setRenderHint(QPainter.Antialiasing)
        for cx, cy, rad, col, a in ((0.18, 0.12, 0.55, "#7B3CFF", 120), (0.92, 0.9, 0.6, "#00B7FF", 70),
                                   (0.78, 0.18, 0.35, "#FF3FD0", 70), (0.45, 0.75, 0.45, "#5A2BD8", 60),
                                   (0.05, 0.85, 0.3, "#00E1C8", 40)):
            rg = QRadialGradient(QPointF(cx * neb.width(), cy * neb.height()), rad * max(w, h))
            c1 = QColor(col)
            c1.setAlpha(a)
            c2 = QColor(col)
            c2.setAlpha(0)
            rg.setColorAt(0, c1)
            rg.setColorAt(0.45, QColor(c1.red(), c1.green(), c1.blue(), a // 3))
            rg.setColorAt(1, c2)
            p.fillRect(neb.rect(), rg)
        p.end()
        # 3. aurora ribbon (two widths of the window, scrolled sideways)
        aw = w * 2
        aur = QPixmap(aw, int(h * 0.55))
        aur.fill(Qt.transparent)
        p = QPainter(aur)
        p.setRenderHint(QPainter.Antialiasing)
        for k, (col, amp, off, thick, alpha) in enumerate((("#3EF0FF", 0.10, 0.55, 0.22, 46), ("#8B5CFF", 0.13, 0.62, 0.30, 40),
                                                            ("#FF4FD8", 0.08, 0.7, 0.16, 28))):
            path = QPainterPath()
            ah = aur.height()
            pts = []
            for i in range(0, 241):
                x = aw * i / 240
                y = ah * off + ah * amp * math.sin(i / 240 * 4 * math.pi + k) + ah * amp * 0.4 * math.sin(i / 240 * 10 * math.pi + k * 2)
                pts.append((x, y))
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            for x, y in reversed(pts):
                path.lineTo(x, y - ah * thick)
            path.closeSubpath()
            lg = QLinearGradient(0, ah * (off - thick), 0, ah * off)
            c = QColor(col)
            lg.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 0))
            lg.setColorAt(0.75, QColor(c.red(), c.green(), c.blue(), alpha))
            lg.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 0))
            p.fillPath(path, lg)
        p.end()
        self.twinkles = [(self.rnd.random() * w, self.rnd.random() * h, self.rnd.uniform(1.0, 2.2), self.rnd.uniform(0.6, 2.2),
                          self.rnd.uniform(0, 6.28)) for _ in range(max(24, n // 12))]
        self._layers = (sky, neb, aur)

    def paintEvent(self, _):
        if self._size != (self.width(), self.height()) or self._layers is None:
            self._build()
        sky, neb, aur = self._layers
        t = time.monotonic() - self._t0 if self.timer.isActive() else 0.0
        p = QPainter(self)
        p.drawPixmap(0, 0, sky)
        w, h = self.width(), self.height()
        dx = -w * 0.1 + math.sin(t / 23) * w * 0.06
        dy = -h * 0.1 + math.cos(t / 31) * h * 0.06
        p.drawPixmap(int(dx), int(dy), neb)
        ax = -((t * 14) % w)
        p.setOpacity(0.85 + 0.15 * math.sin(t / 5))
        p.drawPixmap(int(ax), int(h * 0.42), aur)
        p.setOpacity(1)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for x, y, r, sp, ph in self.twinkles:
            a = 0.5 + 0.5 * math.sin(t * sp + ph)
            c = QColor(255, 255, 255, int(40 + 200 * a))
            p.setBrush(c)
            p.drawEllipse(QPointF(x, y), r * (0.6 + 0.4 * a), r * (0.6 + 0.4 * a))
            if a > 0.9 and r > 1.7:                               # tiny cross-flare on the brightest
                p.setPen(QPen(QColor(200, 240, 255, int(120 * a)), 0.8))
                p.drawLine(QPointF(x - r * 3, y), QPointF(x + r * 3, y))
                p.drawLine(QPointF(x, y - r * 3), QPointF(x, y + r * 3))
                p.setPen(Qt.NoPen)
        p.end()


class Orb(QWidget):
    """A glowing ringed planet for the welcome screen (slowly turning ring, softly pulsing atmosphere)."""

    def __init__(self, size=220, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._t0 = time.monotonic()
        self.timer = QTimer(self, interval=40, timeout=self.update)

    def showEvent(self, e):
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _):
        t = time.monotonic() - self._t0
        s = self.width()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(s / 2, s / 2)
        R = s * 0.27
        pulse = 0.5 + 0.5 * math.sin(t * 1.3)
        halo = QRadialGradient(c, R * 1.9)
        halo.setColorAt(0, QColor(139, 92, 255, int(110 + 40 * pulse)))
        halo.setColorAt(0.55, QColor(62, 240, 255, 35))
        halo.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(c, R * 1.9, R * 1.9)
        tilt = -16 + 3 * math.sin(t * 0.4)

        def ring(back: bool):
            p.save()
            p.translate(c)
            p.rotate(tilt)
            path = QPainterPath()
            rect = QRectF(-R * 1.75, -R * 0.42, R * 3.5, R * 0.84)
            if back:
                path.arcMoveTo(rect, 0)
                path.arcTo(rect, 0, 180)
            else:
                path.arcMoveTo(rect, 180)
                path.arcTo(rect, 180, 180)
            for wdt, col in ((R * 0.16, QColor(255, 79, 216, 70)), (R * 0.07, QColor(255, 140, 230, 200)), (R * 0.02, QColor(255, 255, 255, 220))):
                p.setPen(QPen(col, wdt, Qt.SolidLine, Qt.RoundCap))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
            p.restore()

        ring(True)
        body = QRadialGradient(QPointF(c.x() - R * 0.35, c.y() - R * 0.4), R * 1.4)
        body.setColorAt(0, QColor("#C9FDFF"))
        body.setColorAt(0.35, QColor("#56C8FF"))
        body.setColorAt(0.7, QColor("#7A3DF0"))
        body.setColorAt(1, QColor("#1E0A4A"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(body))
        p.drawEllipse(c, R, R)
        # cloud bands
        p.save()
        clip = QPainterPath()
        clip.addEllipse(c, R, R)
        p.setClipPath(clip)
        for k in range(4):
            y = c.y() - R * 0.6 + k * R * 0.38
            off = math.sin(t * 0.5 + k) * R * 0.2
            p.setBrush(QColor(255, 255, 255, 22 if k % 2 else 14))
            p.drawEllipse(QPointF(c.x() + off, y), R * 1.3, R * 0.09)
        p.restore()
        ring(False)
        # moon
        a = t * 0.6
        mx, my = c.x() + math.cos(a) * R * 2.05, c.y() + math.sin(a) * R * 0.55
        mg = QRadialGradient(QPointF(mx - 3, my - 3), R * 0.2)
        mg.setColorAt(0, QColor("#FFF3C9"))
        mg.setColorAt(1, QColor("#FFB347"))
        p.setBrush(QBrush(mg))
        p.drawEllipse(QPointF(mx, my), R * 0.11, R * 0.11)
        p.end()


class GradientLabel(QLabel):
    """Title text filled with the cyan → violet → magenta gradient."""

    def __init__(self, text="", size=26, weight=QFont.Black, colors=("#3EF0FF", "#8B5CFF", "#FF4FD8"), parent=None):
        super().__init__(text, parent)
        css_w = {QFont.Black: 900, QFont.ExtraBold: 800, QFont.Bold: 700, QFont.DemiBold: 600}.get(weight, 700)
        self.setStyleSheet(f"font-family: 'Segoe UI Variable Display', 'Segoe UI', 'Inter', 'Vazirmatn'; "
                           f"font-size: {size}pt; font-weight: {css_w}; background: transparent;")
        self.colors = colors
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        fm = self.fontMetrics()
        text = fm.elidedText(self.text(), Qt.ElideRight, max(10, self.width() - 8))
        tw = fm.horizontalAdvance(text)
        x = {Qt.AlignHCenter: (self.width() - tw) / 2, Qt.AlignRight: self.width() - tw}.get(
            self.alignment() & (Qt.AlignHCenter | Qt.AlignRight), 0)
        g = QLinearGradient(x, 0, x + max(tw, 1), 0)
        for i, col in enumerate(self.colors):
            g.setColorAt(i / max(1, len(self.colors) - 1), QColor(col))
        path = QPainterPath()
        path.addText(QPointF(x, (self.height() + fm.ascent() - fm.descent()) / 2), self.font(), text)
        glow = QColor(self.colors[1])
        for wdt, a in ((7, 26), (3.5, 46)):
            glow.setAlpha(a)
            p.strokePath(path, QPen(glow, wdt, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.fillPath(path, QBrush(g))
        p.end()

    def sizeHint(self):
        self.ensurePolished()
        s = super().sizeHint()
        s.setHeight(self.fontMetrics().height() + 10)
        s.setWidth(self.fontMetrics().horizontalAdvance(self.text()) + 16)
        return s

    def minimumSizeHint(self):
        return self.sizeHint()
