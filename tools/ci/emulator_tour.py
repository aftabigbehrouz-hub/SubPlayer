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
00:00:00,000 --> 00:00:04,800
Das Wetter im Norden ist gemeldet worden.

2
00:00:05,000 --> 00:00:09,800
Das Wetter im Süden ist geprüft worden.

3
00:00:10,000 --> 00:00:14,800
Das Wetter am Wochenende ist besprochen worden.

4
00:00:15,000 --> 00:00:19,800
Das Wetter für morgen ist berechnet worden.

5
00:00:20,000 --> 00:00:24,800
Das Wetter im Gebirge ist beobachtet worden.

6
00:00:25,000 --> 00:00:29,800
Das Wetter an der Küste ist gemessen worden.

7
00:00:30,000 --> 00:00:34,800
Das Wetter in der Stadt ist gezeigt worden.

8
00:00:35,000 --> 00:00:39,800
Das Wetter für heute ist erklärt worden.
"""
OTHER = """1
00:00:02,000 --> 00:00:05,000
Das Wetter in Hamburg bleibt regnerisch.

2
00:00:06,000 --> 00:00:09,000
Auch morgen ist das Wetter wechselhaft.
"""

# the emulator's own launcher sometimes freezes ("Pixel Launcher isn't responding") and covers the app: switch it off
adb("shell", "pm", "disable-user", "--user", "0", "com.google.android.apps.nexuslauncher", check=False)
adb("shell", "settings", "put", "global", "hide_error_dialogs", "1", check=False)
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
                "sine=frequency=330", "-t", "240", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "/tmp/Wetterbericht.mp4"], check=True)
uri = f"file:///data/user/0/{PKG}/files/Wetterbericht.mp4"
def repeat_srt(srt, times, every_s):
    """The same lines again every `every_s` seconds (a slow emulator needs a longer video)."""
    blocks = [b for b in srt.strip().split("\n\n") if b.strip()]
    out, n = [], 0
    for k in range(times):
        for b in blocks:
            lines = b.split("\n")
            def sh(t):
                h, m, rest = t.split(":"); sec, ms = rest.split(",")
                v = ((int(h) * 60 + int(m)) * 60 + int(sec)) * 1000 + int(ms) + k * every_s * 1000
                return f"{v // 3600000:02d}:{v // 60000 % 60:02d}:{v // 1000 % 60:02d},{v % 1000:03d}"
            a, b2 = [x.strip() for x in lines[1].split("-->")]
            n += 1
            out.append(f"{n}\n{sh(a)} --> {sh(b2)}\n" + "\n".join(lines[2:]))
    return "\n\n".join(out) + "\n"
open("/tmp/a.srt", "w", encoding="utf-8").write(repeat_srt(SRT, 6, 40))
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
def clock():
    ts = [n["text"] for n in nodes() if re.fullmatch(r"\d+:\d\d", n["text"] or "")]
    return ts[0] if ts else "?"
time.sleep(4)                                # let the video load and play


def toggles():
    """What each Space press did, from the app's own log: 'pause' (it was playing) or 'play'."""
    log = adb("logcat", "-d", "-s", "SubPlayer:D", check=False)
    return ["pause" if "playWhenReady=true" in ln else "play" for ln in log.splitlines() if "play/pause:" in ln]


def press_space(n_before):
    adb("shell", "input", "keyevent", "62")
    for _ in range(30):                      # a slow emulator delivers the key seconds later
        t = toggles()
        if len(t) > n_before:
            return t
        time.sleep(1)
    return toggles()


t = press_space(0)
print("  Space pauses:", "yes" if t[:1] == ["pause"] else f"NO {t}")
if t[:1] != ["pause"]:
    problems.append("Space did not pause")
time.sleep(2); a = clock(); time.sleep(3); b = clock()
print(f"  the video stands still while paused: {'yes' if a == b and a != '?' else 'NO'} ({a} → {b})")
if a != b or a == "?":
    problems.append("the video went on after Space")
t = press_space(1)
print("  Space plays again:", "yes" if t[1:2] == ["play"] else f"NO {t}")
time.sleep(4)
t = press_space(2)                           # paused again for the word cards
print("  paused for the word cards:", "yes" if t[2:3] == ["pause"] else f"NO {t}")
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
    back()
    # "worden" hangs under thousands of verbs in the dictionary file — the card must show its real base word, werden
    if tap("worden"):
        time.sleep(2)
        shot("07b_card_worden")
        if find("werden", timeout=6):
            print("  worden → werden: yes")
        else:
            problems.append("the card of 'worden' does not show 'werden'")
            print("  worden → werden: NO")
        back()
    if tap("Wetter"):
        for _ in range(4):
            if find("Where else is it used?", timeout=2):
                break
            n = find("ENGLISH", timeout=1) or find("Save", timeout=1)
            if n:                                # scroll the card itself, starting on the card
                adb("shell", "input", "swipe", "540", str(n["y"]), "540", str(max(300, n["y"] - 700)), "400")
            time.sleep(1)
        if tap("Where else is it used?"):
            time.sleep(5)
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
    if tap("AI lesson"):
        time.sleep(1)
        tap("Copy question")
        time.sleep(1)
        shot("14b_ai_lesson")
    back()

print("my words")
if tap("My words"):
    time.sleep(2)
    shot("15_my_words")
    if tap("Calendar", contains=True, required=False):
        shot("16_calendar")

# ---- 2.9: the four panels of a word, Pause each line going on by itself, the small video window, Review
print("2.9: word panels")
if tap("Wetter", required=False):
    time.sleep(1.5)
    shot("17_word_panels")
    if tap("DICTIONARY", required=False):
        time.sleep(2.5)
        shot("18_panel_dictionary")
        back()
    if tap("SENTENCES", contains=True, required=False):
        time.sleep(1.5)
        shot("18b_panel_sentences")
        back()
back()                                      # to the player
time.sleep(2)
print("2.9: pause each line")
if tap("Pause each line", required=False):
    shot("19_pause_wait_choice")
    press_space(len(toggles()))             # play
    held = find("Next sentence in", contains=True, timeout=25)
    print("  stops at the end of a sentence:", "yes" if held else "NO")
    if held:
        shot("20_paused_after_sentence")
    else:
        problems.append("Pause each line: no pause at the end of a sentence")
    gone = False
    for _ in range(25):                     # it goes on by itself
        if not find("Next sentence in", contains=True, timeout=1):
            gone = True
            break
        time.sleep(1)
    print("  goes on by itself:", "yes" if gone else "NO")
    if not gone:
        problems.append("Pause each line: did not go on by itself")
    tap("Pause each line", required=False)  # off again
print("2.9: the video on another screen")
if tap("My words", required=False):
    time.sleep(2.5)
    mini = find("Back to the player", timeout=6)
    print("  small video window on My Words:", "yes" if mini else "no (the video was not playing)")
    shot("21_mini_player")
    print("2.9: review")
    if tap("Review", contains=True, required=False):
        time.sleep(2)
        shot("22_review")
        back()

if crashed():
    print(adb("logcat", "-d", "-s", "AndroidRuntime:E", check=False)[-6000:])
    sys.exit("The app crashed")
log = adb("logcat", "-d", check=False)
open(os.path.join(OUT, "logcat.txt"), "w").write(log[-400000:])
print("problems:", problems or "none")
if len(problems) > 2:
    sys.exit("too many problems")
