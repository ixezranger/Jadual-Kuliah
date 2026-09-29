#!/usr/bin/env python3
"""
Muat turun takwim Hijri rasmi JAKIM dan simpan dalam data/hijri-jakim.json.

Takwim Malaysia ditentukan JAKIM (kriteria imkanur rukyah), jadi awal bulan
Hijri boleh berbeza sehari daripada kiraan aritmetik. Skrip ini mengambil
tarikh Hijri harian daripada API e-Solat JAKIM dan menyimpan tarikh MULA
setiap bulan Hijri — cukup untuk mengira mana-mana hari dalam julat itu.

Guna:
    python scripts/kemas_hijri.py                 # tahun semasa + tahun depan
    python scripts/kemas_hijri.py --tahun 2027    # tahun tertentu

Jalankan sekali setahun (atau bila JAKIM mengumumkan pindaan takwim).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.request
from datetime import date, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAIL = ROOT / "data" / "hijri-jakim.json"
API = ("https://www.e-solat.gov.my/index.php?r=esolatApi/takwimsolat"
       "&period=year&zone=SGR01&year={tahun}")

# Singkatan bulan dalam respons e-Solat (Bahasa Melayu).
BULAN = {"Jan": 1, "Feb": 2, "Mac": 3, "Apr": 4, "Mei": 5, "Jun": 6,
         "Jul": 7, "Ogos": 8, "Sep": 9, "Okt": 10, "Nov": 11, "Dis": 12}


def muat_turun(tahun: int) -> list[tuple[date, tuple[int, int, int]]]:
    req = urllib.request.Request(API.format(tahun=tahun),
                                 headers={"User-Agent": "JadualKuliah/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    if str(data.get("status", "")).upper().rstrip("!") != "OK":
        raise SystemExit(f"e-Solat: status tidak OK -> {data.get('status')!r}")

    keluar = []
    for h in data["prayerTime"]:
        d, b, t = h["date"].split("-")
        g = date(int(t), BULAN[b], int(d))
        if g.year != tahun:
            continue
        hy, hm, hd = (int(x) for x in h["hijri"].split("-"))
        keluar.append((g, (hy, hm, hd)))
    if not keluar:
        raise SystemExit(f"takwim {tahun} belum disediakan oleh JAKIM — cuba lagi kemudian")
    return sorted(keluar)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--tahun", type=int, action="append",
                    help="tahun Masihi (boleh diulang). Lalai: tahun ini + depan")
    a = ap.parse_args()
    tahun_list = a.tahun or [date.today().year, date.today().year + 1]

    sedia = json.loads(FAIL.read_text(encoding="utf-8")) if FAIL.exists() else {}
    mula = dict(sedia.get("mula_bulan", {}))
    julat = dict(sedia.get("julat", {}))

    for tahun in tahun_list:
        try:
            hari = muat_turun(tahun)
        except SystemExit as e:
            print(f"  [!] {tahun}: {e}")
            continue
        except OSError as e:
            print(f"  [!] {tahun}: gagal menghubungi e-Solat ({e})")
            continue

        for g, (hy, hm, hd) in hari:
            # hari ke-hd bulan hm -> bulan itu bermula (hd-1) hari sebelumnya
            mula[f"{hy}-{hm:02d}"] = (g - timedelta(days=hd - 1)).isoformat()
        julat[str(tahun)] = [hari[0][0].isoformat(), hari[-1][0].isoformat()]
        print(f"  [OK] {tahun}: {len(hari)} hari "
              f"({hari[0][1][0]}-{hari[0][1][1]:02d} hingga {hari[-1][1][0]}-{hari[-1][1][1]:02d})")

    if not julat:
        raise SystemExit("Tiada data dikemas kini.")

    doc = {
        "_nota": ("Tarikh MULA setiap bulan Hijri mengikut takwim rasmi JAKIM "
                  "(API e-Solat, zon SGR01). Dijana oleh scripts/kemas_hijri.py — "
                  "jangan sunting dengan tangan. Kunci = 'tahunHijri-bulan'."),
        "dikemaskini": date.today().isoformat(),
        "julat": dict(sorted(julat.items())),
        "mula_bulan": dict(sorted(mula.items())),
    }
    FAIL.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n  Ditulis: {FAIL.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
