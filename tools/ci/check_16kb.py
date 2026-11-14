"""Fails the build if any native library in an APK/AAB is not aligned for 16 KB memory pages (Google Play rule)."""
import io
import sys
import zipfile

from elftools.elf.elffile import ELFFile

# --allow NAME: a library known not to be aligned, accepted (warning only) in the files after it.
# Used for libvosk.so in the direct APK only: that APK is not published on Google Play.
bad = 0
allow = set()
args = sys.argv[1:]
paths = []
while args:
    a = args.pop(0)
    if a == "--allow":
        allow.add(args.pop(0))
    else:
        paths.append((a, set(allow)))
for path, allowed in paths:
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.endswith(".so"):
                continue
            elf = ELFFile(io.BytesIO(z.read(name)))
            align = min(s["p_align"] for s in elf.iter_segments() if s["p_type"] == "PT_LOAD")
            ok = align >= 16384
            excused = not ok and name.rsplit("/", 1)[-1] in allowed
            bad += 0 if ok or excused else 1
            tag = "OK  " if ok else ("WARN" if excused else "FAIL")
            print(f"{tag} {path}: {name}  LOAD alignment {align}" + ("  (allowed: not on Google Play)" if excused else ""))
sys.exit(1 if bad else 0)
