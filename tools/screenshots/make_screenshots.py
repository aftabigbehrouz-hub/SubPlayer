"""
Store screenshots for SubPlayer: six screens recreated in the app's own design (colours, layout, real dictionary
entries), shown in a phone frame with a caption. Two caption sets: Persian (Cafe Bazaar / Myket) and English (Google Play).
Output: 1080 x 1920 PNG.   Usage:  python make_screenshots.py OUT_DIR PERSIAN_FONT_DIR
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 2                                   # drawn at 2x, scaled down for smooth edges
W, H = 1080 * S, 1920 * S
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "screens")
FA_DIR = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/fonts/vz/fonts/ttf")
INTER = "/usr/share/fonts/opentype/inter/Inter-{}.otf"

BG = (11, 10, 26); CARD = (24, 21, 44); CARD2 = (33, 29, 60)
WHITE = (255, 255, 255); DIM = (154, 152, 181); FAINT = (95, 92, 125)
CYAN = (34, 228, 255); VIOLET = (139, 92, 255); PINK = (255, 79, 216); GOLD = (255, 209, 102)
BLUE_ART = (90, 169, 255); GREEN = (91, 227, 143); RED = (255, 107, 154)


def f(size, weight="Regular"):
    return ImageFont.truetype(INTER.format(weight), size * S)


def fa(size, weight="Regular"):
    return ImageFont.truetype(str(FA_DIR / f"Vazirmatn-{weight}.ttf"), size * S)


def text(d, xy, s, font, fill, anchor="la", rtl=False):
    kw = {"direction": "rtl", "language": "fa"} if rtl else {}
    d.text((xy[0] * S, xy[1] * S), s, font=font, fill=fill, anchor=anchor, **kw)


def tw(d, s, font, rtl=False):
    kw = {"direction": "rtl", "language": "fa"} if rtl else {}
    return d.textlength(s, font=font, **kw) / S


def rrect(d, box, r, fill=None, outline=None, width=1):
    """Rounded box; see-through colours are blended over what is already drawn."""
    x0, y0, x1, y1 = box
    see_through = any(c is not None and len(c) == 4 and c[3] < 255 for c in (fill, outline))
    if not see_through:
        d.rounded_rectangle((x0 * S, y0 * S, x1 * S, y1 * S), r * S, fill=fill, outline=outline, width=width * S)
        return
    img = d._image
    pad = 4 * S
    bx0, by0 = max(0, int(x0 * S) - pad), max(0, int(y0 * S) - pad)
    bx1, by1 = min(img.width, int(x1 * S) + pad), min(img.height, int(y1 * S) + pad)
    layer = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((x0 * S - bx0, y0 * S - by0, x1 * S - bx0, y1 * S - by0), r * S,
                                            fill=fill, outline=outline, width=width * S)
    img.alpha_composite(layer, (bx0, by0))


def gradient(size, c0, c1, horizontal=False):
    w, h = size
    g = Image.new("RGB", (w, h))
    px = g.load()
    for i in range(w if horizontal else h):
        t = i / max(1, (w if horizontal else h) - 1)
        c = tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
        if horizontal:
            for y in range(h):
                px[i, y] = c
        else:
            for x in range(w):
                px[x, i] = c
    return g


def glow(img, center, radius, color, alpha=110):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
                                  fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius // 2))
    img.alpha_composite(layer)


def pill(d, x, y, label, font, active=False, color=None, h=44, pad=20):
    w = tw(d, label, font) + pad * 2
    if active:
        rrect(d, (x, y, x + w, y + h), h / 2, fill=color or VIOLET)
        text(d, (x + w / 2, y + h / 2), label, font, WHITE, "mm")
    else:
        rrect(d, (x, y, x + w, y + h), h / 2, fill=(255, 255, 255, 18), outline=(255, 255, 255, 40), width=2)
        text(d, (x + w / 2, y + h / 2), label, font, WHITE, "mm")
    return x + w + 12


# ------------------------------------------------------------------ phone screen pieces (screen = 760 x 1600)
SW, SH = 760, 1600


def screen_base():
    img = Image.new("RGBA", (SW * S, SH * S), BG + (255,))
    glow(img, (int(SW * S * 0.15), int(SH * S * 0.25)), 420 * S // 2, VIOLET, 70)
    glow(img, (int(SW * S * 0.9), int(SH * S * 0.85)), 380 * S // 2, CYAN, 45)
    d = ImageDraw.Draw(img)
    text(d, (36, 34), "9:41", f(22, "SemiBold"), WHITE, "lm")
    for i in range(4):                                       # signal bars
        rrect(d, (SW - 150 + i * 10, 40 - i * 5, SW - 143 + i * 10, 44), 2, fill=WHITE)
    rrect(d, (SW - 92, 26, SW - 46, 44), 5, outline=WHITE, width=2)
    rrect(d, (SW - 88, 30, SW - 58, 40), 2, fill=WHITE)
    return img, d


def top_bar(img, d, subtitle):
    # "SubPlayer" in the app's cyan→pink gradient
    t = "SubPlayer"
    font = f(40, "ExtraBold")
    tw_ = int(tw(d, t, font) * S) + 4
    mask = Image.new("L", (tw_, 60 * S), 0)
    ImageDraw.Draw(mask).text((0, 0), t, font=font, fill=255)
    grad = gradient((tw_, 60 * S), CYAN, PINK, horizontal=True).convert("RGBA")
    img.paste(grad, (30 * S, 66 * S), mask)
    text(d, (32, 124), subtitle, f(18), DIM)
    for i, x in enumerate((SW - 210, SW - 160, SW - 110, SW - 60)):   # bar icons
        rrect(d, (x, 80, x + 34, 114), 10, outline=(255, 255, 255, 120), width=2)
    d.ellipse(((SW - 196) * S, 88 * S, (SW - 176) * S, 108 * S), outline=GOLD, width=2 * S)


def video(img, d, y, h=420, dim=False):
    """A stylised evening street scene (no real film frame)."""
    vw = SW
    scene = gradient((vw * S, h * S), (36, 24, 76), (255, 140, 110)).convert("RGBA")
    sd = ImageDraw.Draw(scene)
    sd.ellipse((560 * S, 50 * S, 640 * S, 130 * S), fill=(255, 236, 200, 255))
    import random
    rnd = random.Random(4)
    x = 0
    while x < vw:
        bw = rnd.randint(60, 120); bh = rnd.randint(120, 290)
        col = (24 + rnd.randint(0, 20), 18 + rnd.randint(0, 15), 46 + rnd.randint(0, 25), 255)
        sd.rectangle((x * S, (h - bh) * S, (x + bw) * S, h * S), fill=col)
        for wy in range(h - bh + 20, h - 20, 34):
            for wx in range(x + 12, x + bw - 16, 26):
                if rnd.random() < 0.55:
                    sd.rectangle((wx * S, wy * S, (wx + 12) * S, (wy + 16) * S), fill=(255, 214, 140, 230))
        x += bw + rnd.randint(2, 10)
    if dim:
        scene.alpha_composite(Image.new("RGBA", scene.size, (0, 0, 0, 120)))
    img.alpha_composite(scene, (0, y * S))


def subtitle_line(d, y, parts, size=30):
    """parts: [(text, highlighted)] centred on a dark band."""
    font = f(size, "SemiBold")
    total = sum(tw(d, p, font) for p, _ in parts)
    x = (SW - total) / 2
    rrect(d, (x - 18, y - 8, x + total + 18, y + size + 16), 12, fill=(0, 0, 0, 165))
    for p, hl in parts:
        text(d, (x, y), p, font, GOLD if hl else WHITE)
        x += tw(d, p, font)


def controls(d, y):
    font = f(20, "SemiBold")
    rrect(d, (30, y, SW - 30, y + 6), 3, fill=(255, 255, 255, 40))
    rrect(d, (30, y, 330, y + 6), 3, fill=CYAN)
    d.ellipse((322 * S, (y - 6) * S, 340 * S, (y + 12) * S), fill=WHITE)
    text(d, (30, y + 22), "0:14", f(17), DIM)
    text(d, (SW - 30, y + 22), "3:52", f(17), DIM, "ra")
    x = 36
    for lab in ("Prev", "−5s"):
        x = pill(d, x, y + 60, lab, font)
    cx = x + 40
    d.ellipse(((cx - 38) * S, (y + 44) * S, (cx + 38) * S, (y + 120) * S), fill=VIOLET)
    d.polygon([((cx - 10) * S, (y + 66) * S), ((cx - 10) * S, (y + 98) * S), ((cx + 16) * S, (y + 82) * S)], fill=WHITE)
    x = cx + 54
    for lab in ("+5s", "Next", "0.75×"):
        x = pill(d, x, y + 60, lab, font)


def sheet(img, d, y):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((0, y * S, SW * S, (SH + 40) * S), 40 * S, fill=CARD + (250,))
    img.alpha_composite(layer)
    rrect(d, (SW / 2 - 40, y + 14, SW / 2 + 40, y + 20), 3, fill=(255, 255, 255, 70))


def section(d, x, y, label):
    text(d, (x, y), label, f(17, "Bold"), (178, 150, 255))


# ------------------------------------------------------------------ the six screens
def s_player():
    img, d = screen_base()
    top_bar(img, d, "Tagesschau 20 Uhr.mp4  ·  Deutsch · Accurate")
    video(img, d, 170)
    subtitle_line(d, 520, [("Ich glaube, das ", False), ("Haus", True), (" ist alt.", False)])
    controls(d, 640)
    y = 800
    font = f(19, "SemiBold")
    x = pill(d, 36, y, "A  0:12", font, True, PINK)
    x = pill(d, x, y, "B  0:18", font, True, PINK)
    x = pill(d, x, y, "×", font)
    text(d, (36, y + 62), "Looping 0:12 → 0:18", f(18), DIM)
    x = pill(d, 36, y + 100, "Loop line", font, True, VIOLET)
    pill(d, x, y + 100, "Pause each line", font)
    rrect(d, (30, 1010, SW - 30, 1200), 26, fill=(255, 255, 255, 14), outline=(139, 92, 255, 90), width=2)
    text(d, (60, 1040), "Make subtitles", f(26, "Bold"), WHITE)
    text(d, (60, 1080), "Whisper on your phone · offline · Deutsch / English", f(18), DIM)
    for i, (lab, act) in enumerate((("Fast", False), ("Accurate", True), ("Best", False), ("Online", False))):
        pill(d, 60 + i * 158, 1124, lab, f(18, "SemiBold"), act, CYAN if act else None)
    rrect(d, (30, 1240, SW - 30, 1300), 30, fill=(255, 255, 255, 10))
    text(d, (SW / 2, 1270), "Tap the picture to pause · tap a word to look it up", f(18), DIM, "mm")
    return img


def word_card(lemma, article, pos, ipa, hyph, sections, sentence_parts, lang_btn, en=False):
    img, d = screen_base()
    top_bar(img, d, "Paused · tap a word")
    video(img, d, 170, dim=True)
    subtitle_line(d, 520, sentence_parts)
    sheet(img, d, 640)
    y = 680
    if article:
        col = {"der": BLUE_ART, "die": RED, "das": GREEN}[article]
        text(d, (36, y), article + " ", f(46, "Bold"), col)
        x = 36 + tw(d, article + " ", f(46, "Bold"))
    else:
        x = 36
    text(d, (x, y), lemma, f(46, "Bold"), WHITE)
    y += 70
    text(d, (36, y), pos, f(20, "SemiBold"), CYAN)
    text(d, (36 + tw(d, pos, f(20, "SemiBold")) + 22, y), ipa, f(22), WHITE)
    text(d, (SW - 36, y), hyph, f(18), DIM, "ra")
    y += 52
    x = 36
    rrect(d, (x, y, x + 120, y + 46), 23, fill=VIOLET)
    text(d, (x + 60, y + 23), "Speak", f(19, "SemiBold"), WHITE, "mm")
    x = pill(d, x + 132, y, "Slow", f(19, "SemiBold"), h=46)
    x = pill(d, x, y, "▶ Recording", f(19, "SemiBold"), h=46)
    pill(d, x, y, lang_btn + " ↗", f(19, "SemiBold"), h=46)
    y += 82
    for title, lines, rtl in sections:
        if rtl:
            text(d, (SW - 36, y), title, fa(19, "Bold"), (178, 150, 255), "ra", rtl=True)
            y += 34
            for ln in lines:
                text(d, (SW - 36, y), ln, fa(30, "Medium"), WHITE, "ra", rtl=True)
                y += 50
        else:
            section(d, 36, y, title)
            y += 32
            for ln, sub in lines:
                text(d, (36, y), ln, f(22), WHITE)
                y += 34
                if sub:
                    text(d, (56, y), sub, f(19), DIM)
                    y += 34
        y += 18
    rrect(d, (30, SH - 140, SW / 2 - 8, SH - 80), 30, fill=GOLD)
    text(d, (SW / 4 + 11, SH - 110), "☆  Save", f(22, "Bold"), (20, 16, 40), "mm")
    rrect(d, (SW / 2 + 8, SH - 140, SW - 30, SH - 80), 30, fill=(255, 255, 255, 18), outline=(255, 255, 255, 50), width=2)
    text(d, (SW * 3 / 4 - 11, SH - 110), "Learn more", f(21, "SemiBold"), WHITE, "mm")
    return img


def s_word_de():
    return word_card("Haus", "das", "Noun", "/haʊs/", "Haus", [
        ("ENGLISH", [("1. house", None), ("2. home", None)], False),
        ("فارسی", ["خانه، منزل"], True),
        ("BEDEUTUNGEN", [("1. Gebäude, in dem Menschen wohnen", "Das Haus ist alt.")], False),
    ], [("Ich glaube, das ", False), ("Haus", True), (" ist alt.", False)], "DWDS")


def s_word_en():
    return word_card("journey", None, "Noun", "/ˈdʒɜːni/", "jour·ney", [
        ("DEUTSCH", [("Reise, Fahrt", None)], False),
        ("فارسی", ["سفر"], True),
        ("DEFINITIONS", [("1. An act of travelling from one place", None),
                         ("    to another", "It was a long journey home.")], False),
    ], [("It was a long ", False), ("journey", True), (" home.", False)], "Cambridge")


def s_loop():
    img, d = screen_base()
    top_bar(img, d, "Repeat the hard part")
    video(img, d, 170)
    subtitle_line(d, 520, [("Wir sehen uns ", False), ("morgen", True), (" früh.", False)])
    y = 650
    rrect(d, (30, y, SW - 30, y + 10), 5, fill=(255, 255, 255, 40))
    rrect(d, (250, y - 4, 360, y + 14), 6, fill=PINK)
    for x, lab in ((250, "A"), (360, "B")):
        d.ellipse(((x - 18) * S, (y - 26) * S, (x + 18) * S, (y + 10) * S), fill=PINK)
        text(d, (x, y - 8), lab, f(18, "Bold"), WHITE, "mm")
    text(d, (SW / 2, y + 60), "Looping 0:12 → 0:18", f(24, "SemiBold"), WHITE, "mm")
    font = f(21, "SemiBold")
    x = pill(d, 60, y + 110, "A  0:12", font, True, PINK, h=52)
    x = pill(d, x, y + 110, "B  0:18", font, True, PINK, h=52)
    pill(d, x, y + 110, "×  Stop", font, h=52)
    cards = [("Loop line", "Repeats the current subtitle line"),
             ("Pause each line", "Stops after every line so you can read"),
             ("Shadowing", "Pause after each line to speak it yourself"),
             ("0.75×  ·  0.5×", "Slower speech, same pitch")]
    yy = y + 210
    for i, (t, sub) in enumerate(cards):
        rrect(d, (30, yy, SW - 30, yy + 120), 24, fill=(255, 255, 255, 14), outline=(139, 92, 255, 70 if i else 160), width=2)
        text(d, (60, yy + 28), t, f(24, "Bold"), CYAN if i == 0 else WHITE)
        text(d, (60, yy + 70), sub, f(19), DIM)
        yy += 140
    return img


def s_words():
    img, d = screen_base()
    text(d, (36, 80), "My Words", f(40, "ExtraBold"), WHITE)
    text(d, (36, 134), "24 words · 5 due today", f(19), DIM)
    rrect(d, (30, 180, SW - 30, 300), 26, fill=(255, 255, 255, 14), outline=(255, 209, 102, 110), width=2)
    text(d, (60, 210), "12-day streak", f(28, "Bold"), GOLD)
    text(d, (60, 254), "18 answers today · daily reminder 19:00", f(19), DIM)
    rows = [("das", "Haus", "house · خانه", "reviewed 4× · box 3/7 · in 4 days", GREEN),
            ("", "aufstehen", "to get up · بیدار شدن", "reviewed 6× · box 4/7 · in 7 days", None),
            ("", "journey", "Reise · سفر", "reviewed 2× · box 2/7 · due now", None),
            ("die", "Reise", "journey, trip · سفر", "reviewed 3× · box 2/7 · in 2 days", RED),
            ("der", "Bahnhof", "station · ایستگاه", "reviewed 1× · box 1/7 · due now", BLUE_ART)]
    y = 340
    for art, w, mean, meta, col in rows:
        rrect(d, (30, y, SW - 30, y + 150), 24, fill=CARD2)
        x = 60
        if art:
            text(d, (x, y + 26), art + " ", f(28, "Bold"), col)
            x += tw(d, art + " ", f(28, "Bold"))
        text(d, (x, y + 26), w, f(28, "Bold"), WHITE)
        if w == "journey":
            rrect(d, (SW - 120, y + 26, SW - 60, y + 58), 8, fill=(255, 255, 255, 30))
            text(d, (SW - 90, y + 42), "EN", f(16, "Bold"), CYAN, "mm")
        en, fa_ = mean.split(" · ")
        text(d, (60, y + 74), en + "  ·", f(20), WHITE)
        text(d, (60 + tw(d, en + "  · ", f(20)), y + 70), fa_, fa(21), WHITE, rtl=True)
        text(d, (60, y + 110), meta, f(17), DIM)
        text(d, (SW - 60, y + 110), "▶ video", f(17, "SemiBold"), CYAN, "ra")
        y += 168
    rrect(d, (30, SH - 150, SW - 30, SH - 84), 33, fill=VIOLET)
    text(d, (SW / 2, SH - 117), "Review 5 due words", f(24, "Bold"), WHITE, "mm")
    return img


def s_practice():
    img, d = screen_base()
    text(d, (36, 80), "Practice", f(40, "ExtraBold"), WHITE)
    x = 36
    for lab, act in (("Fill the gap", True), ("Dictation", False), ("der · die · das", False)):
        x = pill(d, x, 140, lab, f(19, "SemiBold"), act, CYAN if act else None)
    text(d, (36, 214), "Question 3 of 10 · score 2", f(19), DIM)
    rrect(d, (30, 260, SW - 30, 720), 30, fill=CARD2, outline=(139, 92, 255, 100), width=2)
    text(d, (SW / 2, 360), "Gestern bin ich sehr früh", f(30, "SemiBold"), WHITE, "mm")
    rrect(d, (SW / 2 - 150, 410, SW / 2 + 150, 470), 14, fill=(91, 227, 143, 40), outline=GREEN, width=3)
    text(d, (SW / 2, 440), "aufgestanden", f(30, "Bold"), GREEN, "mm")
    text(d, (SW / 2, 580), "Yesterday I got up very early.", f(20), DIM, "mm")
    text(d, (SW / 2, 630), "دیروز خیلی زود بیدار شدم.", fa(22), DIM, "mm", rtl=True)
    opts = [("aufgestanden", True), ("gegangen", False), ("geschlafen", False), ("gelaufen", False)]
    y = 770
    for i, (o, right) in enumerate(opts):
        x0 = 30 if i % 2 == 0 else SW / 2 + 8
        yy = y + (i // 2) * 110
        rrect(d, (x0, yy, x0 + SW / 2 - 38, yy + 90), 24,
              fill=(91, 227, 143, 50) if right else (255, 255, 255, 14), outline=GREEN if right else (255, 255, 255, 40), width=3 if right else 2)
        text(d, (x0 + (SW / 2 - 38) / 2, yy + 45), o, f(24, "SemiBold"), WHITE, "mm")
    text(d, (SW / 2, 1040), "✓  Right!", f(32, "Bold"), GREEN, "mm")
    rrect(d, (30, 1100, SW - 30, 1260), 26, fill=(255, 255, 255, 12))
    text(d, (60, 1130), "From your words", f(20, "Bold"), (178, 150, 255))
    text(d, (60, 1172), "Sentences come from your videos and the", f(19), DIM)
    text(d, (60, 1204), "examples you added from ChatGPT, DWDS …", f(19), DIM)
    rrect(d, (SW - 250, SH - 150, SW - 30, SH - 84), 33, fill=VIOLET)
    text(d, (SW - 140, SH - 117), "Next →", f(24, "Bold"), WHITE, "mm")
    return img


SCREENS = [s_player, s_word_de, s_word_en, s_loop, s_words, s_practice]
CAPTIONS = {
    "fa": [("زیرنویس آلمانی و انگلیسی", "برای ویدئوهای خودتان، آفلاین روی گوشی"),
           ("معنی هر واژه با یک لمس", "آلمانی به انگلیسی و فارسی، با تلفظ و مثال"),
           ("انگلیسی هم یاد بگیرید", "تعریف انگلیسی، معادل آلمانی و فارسی"),
           ("تکرار مثل VLC", "حلقهٔ A-B، تکرار سطر، مکث بعد از هر سطر"),
           ("واژه‌ها یادتان می‌ماند", "مرور فاصله‌دار با همان لحظهٔ ویدئو"),
           ("تمرین کنید", "جای خالی، دیکته و der · die · das")],
    "en": [("Subtitles for your own videos", "German & English · offline on your phone"),
           ("Tap any word", "Meaning, IPA, examples · English & Persian"),
           ("Learn English too", "Definitions with German & Persian"),
           ("Repeat like VLC", "A-B loop · loop a line · pause each line"),
           ("Remember what you learn", "Spaced review with the video moment"),
           ("Practice", "Gap-fill · dictation · der · die · das")],
}


def compose(screen, title, sub, lang):
    canvas = gradient((W, H), (16, 10, 40), (8, 22, 44)).convert("RGBA")
    glow(canvas, (int(W * 0.2), int(H * 0.12)), 520 * S // 2, VIOLET, 120)
    glow(canvas, (int(W * 0.85), int(H * 0.9)), 520 * S // 2, CYAN, 70)
    d = ImageDraw.Draw(canvas)
    rtl = lang == "fa"
    if rtl:
        text(d, (540, 150), title, fa(66, "Black"), WHITE, "mm", rtl=True)
        text(d, (540, 250), sub, fa(36, "Medium"), (200, 196, 230), "mm", rtl=True)
    else:
        text(d, (540, 150), title, f(62, "ExtraBold"), WHITE, "mm")
        text(d, (540, 250), sub, f(34, "Medium"), (200, 196, 230), "mm")
    # phone: body 840 x 1640 at (120, 360); screen 760 x 1600 inset
    px, py, pw, ph = 120, 350, 840, 1680
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(((px + 10) * S, (py + 30) * S, (px + pw + 10) * S, (py + ph + 30) * S), 110 * S, fill=(0, 0, 0, 170))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(40 * S)))
    rrect(d, (px, py, px + pw, py + ph), 110, fill=(30, 30, 38))
    rrect(d, (px + 6, py + 6, px + pw - 6, py + ph - 6), 104, fill=(8, 8, 12))
    sx, sy = px + 40, py + 40
    mask = Image.new("L", (SW * S, SH * S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, SW * S, SH * S), 76 * S, fill=255)
    canvas.paste(screen, (sx * S, sy * S), mask)
    rrect(d, (sx + SW / 2 - 70, sy + 18, sx + SW / 2 + 70, sy + 54), 18, fill=(0, 0, 0))   # camera notch
    return canvas.resize((1080, 1920), Image.LANCZOS).convert("RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    screens = [fn() for fn in SCREENS]
    for lang, caps in CAPTIONS.items():
        folder = OUT / ("Persian (Bazaar, Myket)" if lang == "fa" else "English (Google Play)")
        folder.mkdir(exist_ok=True)
        for i, (scr, (t, s)) in enumerate(zip(screens, caps), 1):
            compose(scr, t, s, lang).save(folder / f"{i:02d}-{SCREENS[i - 1].__name__[2:]}.png", optimize=True)
    print("done", OUT)


if __name__ == "__main__":
    main()
