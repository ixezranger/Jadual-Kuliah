#!/usr/bin/env python3
"""
Semak gambar ustaz untuk jadual kuliah bulanan.

Poster merender setiap gambar pada saiz yang SAMA. Itu hanya kelihatan kemas
kalau fail sumbernya sendiri seragam. Skrip ni menyemak dua perkara:

  1. Saiz kanvas — sepatutnya 180 x 220 px, PNG berlatar telus.
  2. Saiz wajah dalam kanvas — kanvas yang sama saiz belum tentu bermakna
     wajahnya sama saiz. Kalau seseorang dipotong lebih rapat, kepalanya akan
     nampak lebih besar daripada yang lain pada poster.

Wajah diukur melalui warna kulit (ruang warna YCrCb). Ukuran LEBAR digunakan,
bukan tinggi — sempadan atas wajah tidak menentu kerana kopiah, serban dan
cermin mata, jadi tinggi memberi bacaan yang tidak stabil.

Ukuran ini anggaran, bukan mutlak. Guna sebagai penunjuk fail mana perlu
dipotong semula, bukan sebagai nombor mutlak.

Perlukan numpy (pip install numpy).

    python scripts/semak_gambar.py            # ringkasan + fail tersasar
    python scripts/semak_gambar.py --semua    # senarai penuh setiap fail
"""
from __future__ import annotations

import argparse
import pathlib
import statistics
import sys

import numpy as np
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
FOLDER = ROOT / "assets/ustaz"

KANVAS = (180, 220)      # saiz piawai
TOLERANSI = 0.12         # wajah dianggap tersasar kalau lari > 12% dari median


def ukur(path: pathlib.Path):
    """Pulang (saiz_kanvas, lebar_wajah) atau None kalau wajah tak dapat dikesan."""
    im = Image.open(path).convert("RGBA")
    arr = np.array(im)
    alfa = arr[..., 3]

    ys, _ = np.nonzero(alfa > 40)
    if len(ys) == 0:
        return im.size, None
    y0, y1 = ys.min(), ys.max()

    rgb = arr[..., :3].astype(np.int16)
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    Y = 0.299 * R + 0.587 * G + 0.114 * B
    Cr = (R - Y) * 0.713 + 128
    Cb = (B - Y) * 0.564 + 128

    kulit = ((alfa > 40) & (Cr > 135) & (Cr < 180)
             & (Cb > 85) & (Cb < 135) & (Y > 60))
    kulit[y0 + int((y1 - y0) * 0.65):, :] = False    # elak tangan / dada

    ys2, xs2 = np.nonzero(kulit)
    if len(ys2) < 50:
        return im.size, None
    ylo, yhi = np.percentile(ys2, [3, 97])

    # lebar pipi = persentil 85 lebar baris dalam zon wajah
    lebar = [r[-1] - r[0] for y in range(int(ylo), int(yhi) + 1)
             for r in (np.nonzero(kulit[y])[0],) if len(r)]
    if not lebar:
        return im.size, None
    return im.size, float(np.percentile(lebar, 85))


def main() -> None:
    ap = argparse.ArgumentParser(description="Semak keseragaman gambar ustaz.")
    ap.add_argument("--semua", action="store_true", help="senaraikan setiap fail")
    a = ap.parse_args()

    salah_saiz, tak_dikesan, wajah = [], [], []

    for p in sorted(FOLDER.glob("*.png")):
        saiz, lebar = ukur(p)
        if saiz != KANVAS:
            salah_saiz.append((p.name, saiz))
        if lebar is None:
            tak_dikesan.append(p.name)
        else:
            wajah.append((p.name, lebar, saiz == KANVAS))

    jumlah = len(salah_saiz) + len(tak_dikesan) + len(wajah)
    print(f"\n  {FOLDER.relative_to(ROOT)} — {len(list(FOLDER.glob('*.png')))} fail PNG\n")

    if salah_saiz:
        print(f"  [!] Bukan {KANVAS[0]}x{KANVAS[1]} ({len(salah_saiz)} fail) — potong semula:")
        for n, s in salah_saiz:
            print(f"        {n:<44}{s[0]}x{s[1]}")
        print()
    else:
        print(f"  [OK] Semua fail {KANVAS[0]}x{KANVAS[1]}\n")

    if tak_dikesan:
        print(f"  [?] Wajah tidak dapat dikesan ({len(tak_dikesan)}): "
              f"{', '.join(tak_dikesan)}\n")

    if not wajah:
        return

    nilai = [w for _, w, _ in wajah]
    med = statistics.median(nilai)
    print(f"  Lebar wajah : {min(nilai):.0f}-{max(nilai):.0f}px   median {med:.0f}px"
          f"   beza {max(nilai)/min(nilai):.2f}x")

    tersasar = sorted((abs(w - med) / med, n, w) for n, w, _ in wajah)
    luar = [(d, n, w) for d, n, w in tersasar if d > TOLERANSI]

    if luar:
        print(f"\n  [!] {len(luar)} fail lari lebih {TOLERANSI:.0%} dari median"
              f" — wajahnya akan nampak besar/kecil berbanding yang lain:")
        for d, n, w in sorted(luar, key=lambda t: -t[0]):
            arah = "terlalu BESAR" if w > med else "terlalu kecil"
            print(f"        {n:<44}{w:5.0f}px  {arah} ({(w-med)/med:+.0%})")
        print("\n      Betulkan dengan memotong semula fail berkenaan supaya kepala"
              "\n      mengambil bahagian bingkai yang sama seperti fail lain.")
    else:
        print(f"\n  [OK] Semua wajah dalam lingkungan {TOLERANSI:.0%} dari median.")

    if a.semua:
        print("\n  Senarai penuh (diisih ikut lebar wajah):")
        for n, w, ok in sorted(wajah, key=lambda t: t[1]):
            print(f"        {n:<44}{w:5.0f}px{'' if ok else '   (kanvas bukan piawai)'}")


if __name__ == "__main__":
    main()
