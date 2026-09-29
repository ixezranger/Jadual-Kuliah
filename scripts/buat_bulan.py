#!/usr/bin/env python3
"""
Sediakan fail jadual bulanan (data/<tahun>/<MM>-<bulan>.json) separa-automatik.

Yang dikira sendiri oleh skrip ni:
  - bulan, tahun, mula_hari, hari_dalam_bulan   (daripada kalendar)
  - Bacaan Yasin & Tahlil pada setiap hari Khamis
  - slot Subuh + Maghrib pada setiap hari Ahad
  - ejaan nama penceramah dipadankan dengan registry
  - teks tarikh Kuliah Muslimah, cth "6 SEPTEMBER (AHAD)"

Yang MASIH perlu ditaip manusia: nama penceramah ikut tarikh, dalam fail
mentah. Formatnya sengaja dibuat pendek supaya boleh disalin terus daripada
imej kalendar AJK.

    1   UST.IZMIR FAREEZ
    3   #yasin
    6   UST SYUHUD RAZALI | UST.ANAS MALIK      <- subuh | maghrib
    19  #event (Jemputan)

    [muslimat]
    6  | 9:00 PAGI | USTAZAH ADIBAH

Guna:
    python scripts/buat_bulan.py --bulan 2026-09
    python scripts/buat_bulan.py --bulan 2026-09 --mentah input/2026/09-september/jadual-mentah.txt
    python scripts/buat_bulan.py --bulan 2026-09 --mentah <fail> --tulis
    python scripts/buat_bulan.py --semak data/2026/09-september.json

Tanpa --tulis, skrip hanya memaparkan pratonton dan laporan semakan.
"""
from __future__ import annotations

import argparse
import calendar
import difflib
import json
import pathlib
import re
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent

BULAN_MS = ["JANUARI", "FEBRUARI", "MAC", "APRIL", "MEI", "JUN",
            "JULAI", "OGOS", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DISEMBER"]

# Isnin=0 ... Ahad=6 — sama dengan date.weekday() Python, jadi tiada penukaran.
HARI_MS = ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT", "SABTU", "AHAD"]

KHAMIS, AHAD = 3, 6
TEKS_YASIN = "Bacaan\nYasin & Tahlil\nImam Bertugas"

# Token yang tidak membezakan orang — dibuang sebelum padanan nama.
GELARAN = {"USTAZ", "UST", "USTZ", "USTAZAH", "USTZH", "USTH",
           "DR", "HJ", "HAJI", "LT", "KOL", "BIN", "BINTI", "AL"}


# --------------------------------------------------------------------------
# Padanan nama
# --------------------------------------------------------------------------
def token(nama: str) -> list[str]:
    """Pecah nama kepada token bermakna sahaja (gelaran dibuang)."""
    bersih = re.sub(r"[^A-Z0-9 ]+", " ", nama.upper())
    return [t for t in bersih.split() if t and t not in GELARAN]


def kunci(nama: str) -> str:
    return "".join(token(nama))


def padan(mentah: str, senarai: list[str]) -> tuple[str | None, float, str]:
    """
    Cari nama kanonikal paling hampir.
    Pulang (nama, skor, tahap) — tahap: tepat | auto | sahkan | tiada.
    """
    k = kunci(mentah)
    if not k:
        return None, 0.0, "tiada"

    calon = []
    for n in senarai:
        kn = kunci(n)
        skor = difflib.SequenceMatcher(None, k, kn).ratio()
        # Token yang sama persis ialah bukti kuat — naikkan skor sedikit.
        tm, tn = token(mentah), token(n)
        sama = set(tm) & set(tn)
        if len(sama) >= 2:
            skor = max(skor, 0.90)
        elif len(sama) == 1 and len(tm) == 1:
            skor = max(skor, 0.88)

        # Nama dipendekkan pada poster (cth "LUTFFI" untuk "LUTFI ISMAIL"):
        # setiap token mentah ada padanan hampir dalam nama penuh.
        if tm and all(max((difflib.SequenceMatcher(None, a, b).ratio()
                           for b in tn), default=0) >= 0.85 for a in tm):
            skor = max(skor, 0.90 if len(tm) >= 2 else 0.70)

        calon.append((skor, n))

    calon.sort(reverse=True)
    skor, nama = calon[0]

    if kunci(nama) == k:
        return nama, 1.0, "tepat"
    if skor >= 0.86:
        return nama, skor, "auto"
    if skor >= 0.62:
        return nama, skor, "sahkan"
    return None, skor, "tiada"


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
def muat_registry() -> tuple[list[str], set[str], set[str]]:
    pm = json.loads((ROOT / "data/penceramah-master.json").read_text(encoding="utf-8"))
    um = json.loads((ROOT / "data/ustaz-master.json").read_text(encoding="utf-8"))
    uz = json.loads((ROOT / "data/ustazah-master.json").read_text(encoding="utf-8"))
    penceramah = list(pm.get("penceramah", pm).keys())
    ustaz = {k for k in um if not k.startswith("_")}
    ustazah = {k for k in uz if not k.startswith("_")}
    return penceramah, ustaz, ustazah


# --------------------------------------------------------------------------
# Baca fail mentah
# --------------------------------------------------------------------------
def baca_mentah(path: pathlib.Path) -> tuple[dict[int, dict], list[tuple[int, str, str]]]:
    return baca_mentah_teks(path.read_text(encoding="utf-8"))


def baca_mentah_teks(teks: str) -> tuple[dict[int, dict], list[tuple[int, str, str]]]:
    jadual: dict[int, dict] = {}
    muslimat: list[tuple[int, str, str]] = []
    bahagian = "jadual"

    for no, baris in enumerate(teks.splitlines(), 1):
        baris = baris.strip()
        if not baris or baris.startswith("#!") or baris.startswith("//"):
            continue
        if baris.lower().startswith("[muslimat"):
            bahagian = "muslimat"
            continue
        if baris.lower().startswith("[jadual"):
            bahagian = "jadual"
            continue

        if bahagian == "muslimat":
            bhg = [x.strip() for x in baris.split("|")]
            if len(bhg) != 3:
                raise SystemExit(f"Baris {no}: muslimat perlu 'hari | jam | nama'")
            muslimat.append((int(bhg[0]), bhg[1], bhg[2]))
            continue

        m = re.match(r"^(\d{1,2})(?:\s+(.*))?$", baris)
        if not m:
            raise SystemExit(f"Baris {no}: tidak faham -> {baris!r}")
        hari, isi = int(m.group(1)), (m.group(2) or "").strip()
        if not isi:
            continue  # nombor hari sahaja — ikut corak lalai hari itu

        if isi.lower().startswith("#yasin"):
            jadual[hari] = {"event": TEKS_YASIN}
        elif isi.lower().startswith("#event"):
            jadual[hari] = {"event": isi[6:].strip()}
        elif "|" in isi:
            subuh, maghrib = [x.strip() for x in isi.split("|", 1)]
            jadual[hari] = {"subuh": subuh, "maghrib": maghrib}
        else:
            jadual[hari] = {"maghrib": isi}

    return jadual, muslimat


# --------------------------------------------------------------------------
# Bina struktur bulan
# --------------------------------------------------------------------------
def bina(tahun: int, bulan: int, mentah_jadual: dict[int, dict],
         mentah_muslimat: list[tuple[int, str, str]],
         penceramah: list[str], ustazah: set[str]) -> tuple[dict, list[dict]]:
    hari_akhir = calendar.monthrange(tahun, bulan)[1]
    mula = date(tahun, bulan, 1).weekday()
    nama_bulan = BULAN_MS[bulan - 1]
    laporan: list[dict] = []

    def selesai(mentah_nama: str, hari: int, slot: str) -> str:
        if not mentah_nama:
            return ""
        nama, skor, tahap = padan(mentah_nama, penceramah)
        if tahap != "tepat":
            laporan.append({"hari": hari, "slot": slot, "mentah": mentah_nama,
                            "nama": nama, "skor": skor, "tahap": tahap})
        return nama if nama else mentah_nama

    jadual: dict[str, dict] = {}
    for h in range(1, hari_akhir + 1):
        hw = date(tahun, bulan, h).weekday()
        asal = mentah_jadual.get(h)

        if asal is None:
            # tiada input mentah — isi corak lalai mengikut hari
            if hw == KHAMIS:
                jadual[str(h)] = {"event": TEKS_YASIN}
            elif hw == AHAD:
                jadual[str(h)] = {"subuh": "", "maghrib": ""}
            else:
                jadual[str(h)] = {"maghrib": ""}
            continue

        if "event" in asal:
            jadual[str(h)] = {"event": asal["event"]}
        elif "subuh" in asal:
            jadual[str(h)] = {"subuh": selesai(asal["subuh"], h, "subuh"),
                              "maghrib": selesai(asal["maghrib"], h, "maghrib")}
        else:
            jadual[str(h)] = {"maghrib": selesai(asal["maghrib"], h, "maghrib")}

    muslimah = []
    for h, jam, nama_mentah in mentah_muslimat:
        hw = date(tahun, bulan, h).weekday()
        nama, skor, tahap = padan(nama_mentah, sorted(ustazah))
        if tahap != "tepat":
            laporan.append({"hari": h, "slot": "muslimah", "mentah": nama_mentah,
                            "nama": nama, "skor": skor, "tahap": tahap})
        muslimah.append({"tarikh": f"{h} {nama_bulan} ({HARI_MS[hw]})",
                         "jam": jam, "nama": nama or nama_mentah})

    doc = {
        "bulan": nama_bulan,
        "tahun": str(tahun),
        "mula_hari": mula,
        "_nota_mula_hari": (
            f"1 {nama_bulan.title()} jatuh hari apa? Isnin=0, Selasa=1, Rabu=2, "
            f"Khamis=3, Jumaat=4, Sabtu=5, Ahad=6. 1 {nama_bulan.title()} {tahun} "
            f"= {HARI_MS[mula].title()} = {mula}."),
        "hari_dalam_bulan": hari_akhir,
        "jadual": jadual,
        "muslimah": muslimah,
    }
    return doc, laporan


# --------------------------------------------------------------------------
# Tulis JSON ikut gaya fail sedia ada
# --------------------------------------------------------------------------
def jadi_teks(doc: dict) -> str:
    j = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    b = ["{",
         f'  "bulan": {j(doc["bulan"])},',
         f'  "tahun": {j(doc["tahun"])},',
         f'  "mula_hari": {doc["mula_hari"]},',
         f'  "_nota_mula_hari": {j(doc.get("_nota_mula_hari", ""))},',
         f'  "hari_dalam_bulan": {doc["hari_dalam_bulan"]},',
         "", '  "jadual": {']

    kunci_hari = sorted(doc["jadual"], key=int)
    lebar = max(len(j(k)) + 1 for k in kunci_hari)
    for i, k in enumerate(kunci_hari):
        isi = doc["jadual"][k]
        bhg = ", ".join(f"{j(kk)}: {j(vv)}" for kk, vv in isi.items())
        koma = "" if i == len(kunci_hari) - 1 else ","
        b.append(f'    {(j(k) + ":").ljust(lebar)} {{ {bhg} }}{koma}')
    b.append("  },")

    b.append("")
    if doc.get("muslimah"):
        b.append('  "muslimah": [')
        for i, m in enumerate(doc["muslimah"]):
            koma = "" if i == len(doc["muslimah"]) - 1 else ","
            b.append(f'    {{ "tarikh": {j(m["tarikh"])}, "jam": {j(m["jam"])}, '
                     f'"nama": {j(m["nama"])} }}{koma}')
        b.append("  ]")
    else:
        b.append('  "muslimah": []')
    b.append("}")
    return "\n".join(b) + "\n"


# --------------------------------------------------------------------------
# Laporan
# --------------------------------------------------------------------------
def semakan(doc: dict, laporan: list[dict], ustaz: set[str]) -> dict:
    """Kumpul semua isu dalam bentuk data — dikongsi CLI dan dashboard."""
    return {
        "auto": [r for r in laporan if r["tahap"] == "auto"],
        "sahkan": [r for r in laporan if r["tahap"] == "sahkan"],
        "tiada": [r for r in laporan if r["tahap"] == "tiada"],
        "hilang": sorted({v.get(s) for v in doc["jadual"].values()
                          for s in ("subuh", "maghrib") if v.get(s)} - ustaz),
        "separa": [k for k, v in doc["jadual"].items()
                   if "event" not in v and any(v.values()) and not all(v.values())],
        "kosong": [k for k, v in doc["jadual"].items()
                   if "event" not in v and not any(v.values())],
    }


def cetak_laporan(doc: dict, laporan: list[dict], ustaz: set[str]) -> int:
    perlu = 0
    s = semakan(doc, laporan, ustaz)
    auto, sahkan, tiada = s["auto"], s["sahkan"], s["tiada"]
    hilang, separa, kosong = s["hilang"], s["separa"], s["kosong"]

    if auto:
        print("\n  Ejaan diseragamkan sendiri:")
        for r in auto:
            print(f"    {r['hari']:>2} {r['slot']:<8} {r['mentah']:<34} -> {r['nama']}")

    if sahkan:
        perlu += len(sahkan)
        print("\n  [!] PERLU DISAHKAN — padanan tidak cukup yakin:")
        for r in sahkan:
            print(f"    {r['hari']:>2} {r['slot']:<8} {r['mentah']:<34} -> {r['nama']}"
                  f"  ({r['skor']:.0%})")

    if tiada:
        perlu += len(tiada)
        print("\n  [!] TIADA DALAM REGISTRY — perlu didaftarkan:")
        for r in tiada:
            print(f"    {r['hari']:>2} {r['slot']:<8} {r['mentah']}")

    if hilang:
        perlu += len(hilang)
        print("\n  [!] ADA DALAM penceramah-master TAPI TIADA DALAM ustaz-master")
        print("      (render jadual bulanan akan gagal):")
        for n in hilang:
            print(f"    {n}")

    if separa:
        perlu += len(separa)
        print(f"\n  [!] Slot separa kosong: hari {', '.join(separa)}")

    if kosong:
        perlu += len(kosong)
        print(f"\n  [!] Hari belum diisi: {', '.join(kosong)}")

    if not perlu:
        print("\n  [OK] Tiada input manual diperlukan. Fail sedia untuk dijana.")
    return perlu


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Sediakan fail jadual bulanan.")
    ap.add_argument("--bulan", help="cth 2026-09")
    ap.add_argument("--mentah", help="fail teks jadual mentah")
    ap.add_argument("--semak", help="semak fail JSON sedia ada, tanpa menulis apa-apa")
    ap.add_argument("--tulis", action="store_true", help="tulis fail (tanpa ini: pratonton sahaja)")
    a = ap.parse_args()

    penceramah, ustaz, ustazah = muat_registry()

    if a.semak:
        p = pathlib.Path(a.semak)
        doc = json.loads(p.read_text(encoding="utf-8"))
        print(f"\n  Semakan: {p}")
        lap = []
        for h, v in doc.get("jadual", {}).items():
            for slot in ("subuh", "maghrib"):
                if v.get(slot):
                    nama, skor, tahap = padan(v[slot], penceramah)
                    if tahap != "tepat":
                        lap.append({"hari": int(h), "slot": slot, "mentah": v[slot],
                                    "nama": nama, "skor": skor, "tahap": tahap})
        perlu = cetak_laporan(doc, lap, ustaz)
        sys.exit(1 if perlu else 0)

    if not a.bulan:
        ap.error("--bulan diperlukan (cth 2026-09)")

    tahun, bulan = (int(x) for x in a.bulan.split("-"))
    mentah_jadual, mentah_muslimat = ({}, [])
    if a.mentah:
        mentah_jadual, mentah_muslimat = baca_mentah(pathlib.Path(a.mentah))

    doc, laporan = bina(tahun, bulan, mentah_jadual, mentah_muslimat, penceramah, ustazah)
    teks = jadi_teks(doc)

    slug = f"{bulan:02d}-{BULAN_MS[bulan - 1].lower()}"
    keluar = ROOT / "data" / str(tahun) / f"{slug}.json"

    print(f"\n  {doc['bulan']} {doc['tahun']}"
          f"  —  1 haribulan = {HARI_MS[doc['mula_hari']].title()}"
          f" (mula_hari={doc['mula_hari']}), {doc['hari_dalam_bulan']} hari")
    print(f"  Sasaran: {keluar.relative_to(ROOT)}")

    perlu = cetak_laporan(doc, laporan, ustaz)

    if a.tulis:
        if keluar.exists():
            print(f"\n  [X] {keluar.name} sudah wujud — padam atau namakan semula dahulu.")
            sys.exit(1)
        keluar.parent.mkdir(parents=True, exist_ok=True)
        keluar.write_text(teks, encoding="utf-8")
        print(f"\n  [OK] Ditulis: {keluar.relative_to(ROOT)}")
    else:
        print("\n  --- pratonton (guna --tulis untuk simpan) ---\n")
        print(teks)

    sys.exit(0)


if __name__ == "__main__":
    main()
