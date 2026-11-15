"""
Walks through the Android app on an emulator (GitHub Actions, .github/workflows/android-emulator.yml) and takes a screenshot of
every new screen of version 2.7. Fails if the app crashes. A small test video ("Wetterbericht") with German subtitles is made with
FFmpeg and put in the app's own folder, so no permissions are needed.

usage: python3 emulator_tour.py app.apk out_dir
"""
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

APK, OUT = sys.argv[1], sys.argv[2]
PKG = "com.behrouz.subplayer"
FILES = f"/sdcard/Android/data/{PKG}/files"
os.makedirs(OUT, exist_ok=True)
problems = []


def adb(*a, check=True, timeout=120):
    r = subprocess.run(["adb", *a], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"adb {' '.join(a)}: {r.stderr.strip()}")
    return r.stdout


def nodes():
    x = ""
    for i in range(4):
        adb("shell", "rm", "-f", "/sdcard/u.xml", check=False)
        r = adb("shell", "uiautomator", "dump", "--compressed", "/sdcard/u.xml", check=False, timeout=60)
        x = adb("shell", "cat", "/sdcard/u.xml", check=False)
        if "<hierarchy" in x:
            break
        print("   (screen not readable yet:", r.strip()[:120], ")")
        time.sleep(2)
    out = []
    try:
        root = ET.fromstring(x[x.index("<hierarchy"):])
    except Exception:
        return out
    for n in root.iter("node"):
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds", ""))
        if not m:
            continue
        a, b, c, d = map(int, m.groups())
        out.append({"text": n.get("text", ""), "desc": n.get("content-desc", ""), "x": (a + c) // 2, "y": (b + d) // 2,
                    "top": b, "bottom": d})
    return out


def find(label, contains=False, timeout=12):
    end = time.time() + timeout
    while time.time() < end:
        ns = nodes()
        anr = next((n for n in ns if "isn't responding" in n["text"]), None)
        if anr:                                      # a slow emulator: "… isn't responding" — wait for it
            w = next((n for n in ns if n["text"] == "Wait"), None)
            if w:
                adb("shell", "input", "tap", str(w["x"]), str(w["y"]))
                time.sleep(3)
                continue
        for n in ns:
            for v in (n["text"], n["desc"]):
                if v and (v == label or (contains and label.lower() in v.lower())):
                    return n
        time.sleep(1)
    return None


def tap(label, contains=False, timeout=12, required=True):
    n = find(label, contains, timeout)
    if not n:
        if required:
            problems.append(f"not found: {label!r}")
            print("  !! not found:", label)
        return False
    adb("shell", "input", "tap", str(n["x"]), str(n["y"]))
    time.sleep(1.2)
    return True


def shot(name):
    """Saves the screen, and prints it as a JPEG in base64 between markers (the log can be read where artifacts can't)."""
    time.sleep(1.0)
    png = os.path.join(OUT, name + ".png")
    with open(png, "wb") as f:
        f.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=60).stdout)
    jpg = os.path.join(OUT, name + ".jpg")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", png, "-vf", "scale=720:-2", "-q:v", "4", jpg], check=False)
    if os.path.exists(jpg):
        import base64
        b = base64.b64encode(open(jpg, "rb").read()).decode()
        print(f"=====SHOT {name}=====")
        for i in range(0, len(b), 4000):
            print(b[i:i + 4000])
        print(f"=====END {name}=====")
    print("  shot", name)


def crashed():
    log = adb("logcat", "-d", "-s", "AndroidRuntime:E", check=False)
    return "FATAL EXCEPTION" in log and PKG in log


def back():
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(1.2)


def java_hash(s: str) -> str:
    h = 0
    for ch in s.encode("utf-16-be").decode("utf-16-be"):
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    return format(h, "x")


SRT = """1
00:00:01,000 --> 00:00:04,000
Guten Abend und willkommen zum Wetterbericht.

2
00:00:04,500 --> 00:00:08,000
Morgen wird das Wetter im Norden sonnig und warm.

3
00:00:08,500 --> 00:00:12,000
Im Süden gibt es Gewitter und starke Niederschläge.

4
00:00:12,500 --> 00:00:16,000
Die Temperaturen steigen auf dreißig Grad.

5
00:00:16,500 --> 00:00:20,000
Am Wochenende kühlt es deutlich ab.

6
00:00:20,500 --> 00:00:24,000
Vergessen Sie Ihren Regenschirm nicht!

7
00:00:24,500 --> 00:00:28,000
Das war das Wetter für heute.

8
00:00:28,500 --> 00:00:40,000
Ich wünsche Ihnen einen schönen Abend.
"""
OTHER = """1
00:00:02,000 --> 00:00:05,000
Das Wetter in Hamburg bleibt regnerisch.

2
00:00:06,000 --> 00:00:09,000
Auch morgen ist das Wetter wechselhaft.
"""

print("install")
adb("install", "-r", "-g", APK, timeout=300)
adb("logcat", "-c")
adb("shell", "am", "start", "-n", f"{PKG}/.MainActivity")
time.sleep(10)
if find("Skip", timeout=40):
    shot("00_tour")
    tap("Skip")
shot("01_home")

print("discover")
if tap("Discover programmes"):
    time.sleep(18)
    shot("02_discover_german")
    tap("English")
    time.sleep(18)
    shot("03_discover_english")
    # a programme's card
    n = find("English in a Minute:", contains=True, timeout=5)
    if n:
        adb("shell", "input", "tap", str(n["x"]), str(n["y"]))
        time.sleep(2)
        shot("04_programme")
        back()
    back()

print("video")
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25", "-f", "lavfi", "-i",
                "sine=frequency=330", "-t", "40", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "/tmp/Wetterbericht.mp4"], check=True)
uri = f"file:///data/user/0/{PKG}/files/Wetterbericht.mp4"
open("/tmp/a.srt", "w", encoding="utf-8").write(SRT)
open("/tmp/b.srt", "w", encoding="utf-8").write(OTHER)
# The files go into the app's own private folder, written by the app's user (run-as works for the debug build): the video,
# and the subtitles as if synced from another device (files/synced_subs/<name>.de.srt) — the app picks them up by file name.
def place(local, rel):
    tmp = "/data/local/tmp/" + os.path.basename(local)
    adb("push", local, tmp)
    d = os.path.dirname(rel)
    adb("shell", f"cat {tmp} | run-as {PKG} sh -c 'mkdir -p {d or '.'} && cat > {rel}'")
place("/tmp/Wetterbericht.mp4", "files/Wetterbericht.mp4")
place("/tmp/a.srt", "files/synced_subs/Wetterbericht.de.srt")
place("/tmp/b.srt", "files/synced_subs/Tagesschau_Wetter.de.srt")
print(adb("shell", f"run-as {PKG} ls -laR files", check=False)[:2000])
adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", uri, "-t", "video/mp4", "-n", f"{PKG}/.MainActivity")
time.sleep(4)
tap("A1–C2")
if not tap("Translation", timeout=4, required=False):
    p = find("Pause each line")
    if p:
        adb("shell", "input", "swipe", "900", str(p["y"]), "200", str(p["y"]), "300")
        time.sleep(1)
    tap("Translation")
adb("shell", "input", "keyevent", "62")      # Space = pause (keyboard)
time.sleep(1)
adb("shell", "input", "keyevent", "62")      # Space = play again
time.sleep(5.5)
adb("shell", "input", "keyevent", "62")      # pause on line 2
time.sleep(2)
shot("05_player_levels_translation")

print(adb("logcat", "-d", "-s", "SubPlayer", check=False)[-3000:])
print("word card")
if tap("Wetter"):
    time.sleep(2)
    shot("06_word_card")
    if tap("Download German dictionary", timeout=5, required=False):
        for _ in range(60):
            time.sleep(5)
            if not find("Downloading", contains=True, timeout=1):
                break
        if not find("Where else is it used?", timeout=10):
            tap("Wetter", required=False)
        time.sleep(3)
        shot("07_word_card_dictionary")
    tap("Save", required=False)
    if tap("Where else is it used?"):
        time.sleep(4)
        shot("08_where_else")
        back()
    else:
        back()

print("options, transcript, edit")
if tap("Options"):
    shot("09_options")
    back()
if tap("Transcript"):
    shot("10_transcript")
    back()
if tap("Edit line"):
    shot("11_edit_line")
    back()

print("study")
if tap("Study video"):
    time.sleep(4)
    shot("12_study_words")
    tap("Practise")
    shot("13_study_practise")
    if tap("Start"):
        time.sleep(2)
        shot("14_gap_from_video")
        back()
    back()

print("my words")
if tap("My words"):
    time.sleep(2)
    shot("15_my_words")
    if tap("Calendar", contains=True, required=False):
        shot("16_calendar")

if crashed():
    print(adb("logcat", "-d", "-s", "AndroidRuntime:E", check=False)[-6000:])
    sys.exit("The app crashed")
log = adb("logcat", "-d", check=False)
open(os.path.join(OUT, "logcat.txt"), "w").write(log[-400000:])
print("problems:", problems or "none")
if len(problems) > 4:
    sys.exit("too many screens not found")
