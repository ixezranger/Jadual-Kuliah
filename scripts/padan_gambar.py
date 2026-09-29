#!/usr/bin/env python3
"""
Padankan fail gambar yang ada dalam folder dengan entri dalam registry.

Masalah yang diselesaikan: gambar sudah dimasukkan ke dalam folder, tetapi
registry belum tahu nama failnya — jadi poster dilangkau walaupun gambar ada.

Skrip ni mengimbas tiga pasangan folder/registry:

    assets/ustaz/*.png                     <-> data/ustaz-master.json
    assets/ustaz/kuliah-individu-ustaz/    <-> data/penceramah-master.json ("tile")
    assets/ustazah/*.png                   <-> data/ustazah-master.json

Nama fail dipadankan dengan nama kanonikal, nama_fail dan nama_poster —
mana-mana yang paling hampir. Ejaan tidak perlu sama.

Guna:
    python scripts/padan_gambar.py                 # laporan sahaja
    python scripts/padan_gambar.py --tulis         # isi padanan yang yakin
    python scripts/padan_gambar.py --tulis --semua # termasuk yang perlu disahkan

Tanpa --tulis, tiada fail diubah.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from buat_bulan import padan  # noqa: E402  (guna pemadan yang sama)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Awalan pada nama fail yang bukan sebahagian daripada nama orang.
AWALAN = ("ki-", "Muslimat-")


def teks_fail(nama_fail: str) -> str:
    """'ki-Ustaz-Mohd-Ihsan-Mohamad-Daud.png' -> 'Ustaz Mohd Ihsan Mohamad Daud'"""
    t = pathlib.Path(nama_fail).stem
    for a in AWALAN:
        if t.lower().startswith(a.lower()):
            t = t[len(a):]
    return re.sub(r"[-_]+", " ", t).strip()


def cari(fail: str, entri: dict[str, list[str]]) -> tuple[str | None, float, str]:
    """
    Padankan satu fail dengan entri registry.
    entri: {nama_kanonikal: [rentetan identiti untuk dibandingkan]}
    """
    t = teks_fail(fail)
    terbaik: tuple[float, str | None, str] = (0.0, None, "tiada")
    for kanon, identiti in entri.items():
        for s in identiti:
            nama, skor, tahap = padan(t, [s])
            if nama and skor > terbaik[0]:
                terbaik = (skor, kanon, tahap)
    skor, kanon, tahap = terbaik
    return kanon, skor, tahap


# --------------------------------------------------------------------------
def imbas(tajuk: str, folder: pathlib.Path, corak: str,
          entri: dict[str, list[str]], semasa: dict[str, str]) -> dict[str, str]:
    """
    Pulang cadangan {nama_kanonikal: nama_fail} untuk entri yang belum berisi.
    """
    print(f"\n{'=' * 72}\n  {tajuk}\n{'=' * 72}")

    if not folder.exists():
        print(f"  Folder tiada: {folder.relative_to(ROOT)}")
        return {}

    fail_ada = sorted(p.name for p in folder.glob(corak))
    print(f"  Folder  : {folder.relative_to(ROOT)}  ({len(fail_ada)} fail)")
    print(f"  Registry: {len(entri)} entri")

    # 1. entri yang sudah ada nama fail — sahkan failnya wujud
    betul, rosak = [], []
    for kanon, f in semasa.items():
        if not f:
            continue
        (betul if f in fail_ada else rosak).append((kanon, f))

    # 2. entri kosong — cuba padankan dengan fail yang belum dituntut
    dituntut = {f for _, f in betul}
    baki = [f for f in fail_ada if f not in dituntut]
    kosong = [k for k in entri if not semasa.get(k)]

    yakin: dict[str, str] = {}
    sahkan: list[tuple[str, str, float]] = []

    for f in baki:
        kanon, skor, tahap = cari(f, {k: entri[k] for k in kosong})
        if not kanon or kanon in yakin:
            continue
        if tahap in ("tepat", "auto"):
            yakin[kanon] = f
        elif tahap == "sahkan":
            sahkan.append((kanon, f, skor))

    yatim = [f for f in baki
             if f not in yakin.values() and f not in [s[1] for s in sahkan]]
    masih = [k for k in kosong if k not in yakin and k not in [s[0] for s in sahkan]]

    print(f"\n  [OK] Sudah betul          : {len(betul)}")
    if rosak:
        print(f"  [!]  Nama fail tidak wujud : {len(rosak)}")
        for k, f in rosak:
            print(f"         {k:<38} -> {f}")
    if yakin:
        print(f"\n  [+] Boleh diisi automatik  : {len(yakin)}")
        for k, f in sorted(yakin.items()):
            print(f"         {k:<38} -> {f}")
    if sahkan:
        print(f"\n  [?] Perlu disahkan         : {len(sahkan)}")
        for k, f, s in sorted(sahkan):
            print(f"         {k:<38} -> {f}  ({s:.0%})")
    if masih:
        print(f"\n  [-] Entri tanpa gambar     : {len(masih)}")
        for k in sorted(masih):
            print(f"         {k}")
    if yatim:
        print(f"\n  [-] Fail tanpa pemilik     : {len(yatim)}")
        print("      (gambar ada, tetapi tiada entri registry yang padan)")
        for f in yatim:
            print(f"         {f}")

    return yakin, {k: f for k, f, _ in sahkan}


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Padankan gambar dengan registry.")
    ap.add_argument("--tulis", action="store_true", help="simpan padanan ke registry")
    ap.add_argument("--semua", action="store_true",
                    help="termasuk padanan 'perlu disahkan'")
    a = ap.parse_args()

    p_um = ROOT / "data/ustaz-master.json"
    p_pm = ROOT / "data/penceramah-master.json"
    p_zm = ROOT / "data/ustazah-master.json"

    um = json.loads(p_um.read_text(encoding="utf-8"))
    pm = json.loads(p_pm.read_text(encoding="utf-8"))
    zm = json.loads(p_zm.read_text(encoding="utf-8"))
    orang = pm["penceramah"]

    # --- jadual bulanan ---
    entri_um = {k: [k] for k in um if not k.startswith("_")}
    kini_um = {k: um[k] for k in entri_um}
    yakin_um, sahkan_um = imbas(
        "1. Jadual bulanan  —  assets/ustaz/",
        ROOT / "assets/ustaz", "*.png", entri_um, kini_um)

    # --- poster individu ---
    entri_pm = {}
    for k, v in orang.items():
        identiti = [k]
        for medan in ("nama_fail", "nama_poster"):
            if v.get(medan):
                identiti.append(v[medan])
        entri_pm[k] = identiti
    kini_pm = {k: (v.get("tile") or "") for k, v in orang.items()}
    yakin_pm, sahkan_pm = imbas(
        "2. Poster kuliah individu  —  assets/ustaz/kuliah-individu-ustaz/",
        ROOT / "assets/ustaz/kuliah-individu-ustaz", "*.png", entri_pm, kini_pm)

    # --- muslimah ---
    entri_zm = {k: [k] for k in zm if not k.startswith("_")}
    kini_zm = {k: zm[k] for k in entri_zm}
    yakin_zm, sahkan_zm = imbas(
        "3. Kuliah muslimah  —  assets/ustazah/",
        ROOT / "assets/ustazah", "*.png", entri_zm, kini_zm)

    if a.semua:
        yakin_um.update(sahkan_um)
        yakin_pm.update(sahkan_pm)
        yakin_zm.update(sahkan_zm)

    jumlah = len(yakin_um) + len(yakin_pm) + len(yakin_zm)
    print(f"\n{'=' * 72}")

    if not a.tulis:
        print(f"  {jumlah} padanan sedia untuk diisi.")
        print("  Jalankan semula dengan --tulis untuk menyimpannya.")
        if sahkan_um or sahkan_pm or sahkan_zm:
            print("  Tambah --semua untuk memasukkan yang bertanda [?] juga.")
        return

    if not jumlah:
        print("  Tiada apa-apa untuk diisi.")
        return

    for k, f in yakin_um.items():
        um[k] = f
    for k, f in yakin_pm.items():
        orang[k]["tile"] = f
    for k, f in yakin_zm.items():
        zm[k] = f

    # Tulis fail yang ada padanan baharu sahaja, dan kekalkan gaya hujung fail
    # asal. Fail tanpa padanan langsung tidak disentuh — kalau tidak, json.dumps
    # akan membuang jarak/susun atur yang ditulis tangan dalam fail itu.
    for p, d, ada in ((p_um, um, yakin_um), (p_pm, pm, yakin_pm), (p_zm, zm, yakin_zm)):
        if not ada:
            continue
        asal = p.read_text(encoding="utf-8")
        baru = json.dumps(d, ensure_ascii=False, indent=2)
        if asal.endswith("\n"):
            baru += "\n"
        if baru == asal:
            continue
        p.write_text(baru, encoding="utf-8")
        print(f"  [OK] Dikemas kini: {p.relative_to(ROOT)}")

    print(f"\n  {jumlah} padanan disimpan.")


if __name__ == "__main__":
    main()
