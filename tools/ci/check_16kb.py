"""Fails the build if any native library in an APK/AAB is not aligned for 16 KB memory pages (Google Play rule)."""
import io
import sys
import zipfile

from elftools.elf.elffile import ELFFile

bad = 0
for path in sys.argv[1:]:
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.endswith(".so"):
                continue
            elf = ELFFile(io.BytesIO(z.read(name)))
            align = min(s["p_align"] for s in elf.iter_segments() if s["p_type"] == "PT_LOAD")
            ok = align >= 16384
            bad += 0 if ok else 1
            print(f"{'OK  ' if ok else 'FAIL'} {path}: {name}  LOAD alignment {align}")
sys.exit(1 if bad else 0)
