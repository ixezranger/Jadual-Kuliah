#!/usr/bin/env python3
"""
Kira 'state' sistem daripada fail sedia ada — tiada pangkalan data.

Sumber kebenaran:
  data/masjid.json                  senarai masjid/surau (CMS)
  data/penceramah-master.json       registry penceramah individu
  data/<tahun>/<MM>-<bulan>.json    jadual bulanan (input)
  input/<tahun>/<MM>-<bulan>/       imej kalendar asal dari AJK
  output/<tahun>/<MM>-<bulan>.png   jadual bulanan (output)
  output/<tahun>/Jadual Kuliah Individu/<MM>-<Bulan>-<tahun>/   poster individu
"""
from __future__ import annotations

import calendar
import pathlib
import re
import sys
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ki_common as K  # noqa: E402


def bulan_slug(bulan: int) -> str:
    """8 -> '08-ogos'"""
    return f"{bulan:02d}-{K.BULAN_MS[bulan - 1].lower()}"


def _tarikh_slot(data: dict, tahun: int, bulan: int) -> list[tuple[date, str, str]]:
    """[(tarikh, slot, nama_kanonikal), ...] daripada jadual bulanan."""
    keluar = []
    for hari_str, info in data.get("jadual", {}).items():
        for slot in ("subuh", "maghrib"):
            nama = info.get(slot)
            if nama:
                keluar.append((date(tahun, bulan, int(hari_str)), slot, nama))
    return keluar


def status_bulan(masjid: dict, tahun: int, bulan: int, master: dict) -> dict:
    """Status penuh satu bulan untuk satu masjid."""
    slug = bulan_slug(bulan)
    nama_bulan = K.BULAN_MS[bulan - 1]

    # --- 1. Sumber: imej kalendar dari AJK ---
    input_dir = K.ROOT / "input" / str(tahun) / slug
    sumber = sorted(
        p.name for p in input_dir.glob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
    ) if input_dir.exists() else []

    # --- 2. Data jadual bulanan ---
    data_path = K.ROOT / "data" / str(tahun) / f"{slug}.json"
    ada_data = data_path.exists()
    data = K.load_json(data_path) if ada_data else {}
    slot_semua = _tarikh_slot(data, tahun, bulan) if ada_data else []

    # Tindihan tajuk per-tarikh — sumber yang SAMA dengan render_individu.py,
    # supaya tajuk yang dipapar dashboard betul-betul tajuk yang akan dicetak.
    ov_path = K.ROOT / "data" / str(tahun) / "individu" / f"{slug}.json"
    tindih = K.load_json(ov_path).get("jadual", {}) if ov_path.exists() else {}

    # --- 3. Output jadual bulanan ---
    out_bulanan = K.ROOT / masjid.get("output_bulanan", f"output/{tahun}")
    png = out_bulanan / f"{slug}.png"
    pdf = out_bulanan / f"{slug}.pdf"
    bulanan = {
        "siap": png.exists(),
        "png": str(png) if png.exists() else None,
        "pdf": str(pdf) if pdf.exists() else None,
        "folder": str(out_bulanan),
        "dikemaskini": (png.stat().st_mtime if png.exists() else None),
    }

    # --- 4. Output kuliah individu ---
    folder_individu = (K.ROOT / masjid["output_root"]
                       / K.nama_folder_bulan(tahun, bulan))
    sedia_ada = ({p.name for p in folder_individu.glob("*.jpg")}
                 if folder_individu.exists() else set())

    dijangka, tiada_gambar, tak_dikenali = [], [], []
    for tarikh, slot, kanon in sorted(slot_semua):
        p = master.get(kanon)
        if p is None:
            tak_dikenali.append({"tarikh": tarikh.isoformat(), "slot": slot,
                                 "nama": kanon})
            continue
        dua_slot = sum(1 for t, _, _ in slot_semua if t == tarikh) > 1
        fail = K.nama_fail_poster(tarikh, p.get("nama_fail") or p["nama_poster"],
                                  slot, dua_slot)
        tile = p.get("tile")
        ada_tile = bool(tile) and (K.ROOT / masjid["ustaz_tile_dir"] / tile).exists()
        ov = tindih.get(str(tarikh.day), {}).get(slot, {})
        rekod = {
            "tarikh": tarikh.isoformat(),
            "slot": slot,
            "kanon": kanon,
            "nama_poster": p["nama_poster"],
            "tajuk": ov.get("tajuk") or p.get("tajuk") or "",
            "tajuk_lalai": p.get("tajuk") or "",
            "tajuk_ditindih": bool(ov.get("tajuk")),
            "fail": fail,
            "ada_gambar": ada_tile,
            "siap": fail in sedia_ada,
        }
        dijangka.append(rekod)
        if not ada_tile:
            tiada_gambar.append(rekod)

    siap = [r for r in dijangka if r["siap"]]
    boleh = [r for r in dijangka if not r["siap"] and r["ada_gambar"]]

    individu = {
        "folder": str(folder_individu),
        "wujud": folder_individu.exists(),
        "jumlah_dijangka": len(dijangka),
        "jumlah_siap": len(siap),
        "jumlah_boleh_jana": len(boleh),
        "jumlah_tertangguh": len(tiada_gambar),
        "senarai": dijangka,
        "tertangguh": tiada_gambar,
        "yatim": sorted(sedia_ada - {r["fail"] for r in dijangka}),
    }

    if not dijangka:
        peringkat = "tiada-data"
    elif individu["jumlah_siap"] == 0:
        peringkat = "belum-mula"
    elif individu["jumlah_siap"] < len(dijangka):
        peringkat = "separuh"
    else:
        peringkat = "selesai"

    return {
        "tahun": tahun,
        "bulan": bulan,
        "slug": slug,
        "nama_bulan": nama_bulan,
        "label": f"{nama_bulan} {tahun}",
        "folder_label": K.nama_folder_bulan(tahun, bulan),
        "sumber": {"folder": str(input_dir), "fail": sumber},
        "ada_data": ada_data,
        "hari_dalam_bulan": calendar.monthrange(tahun, bulan)[1],
        "bulanan": bulanan,
        "individu": individu,
        "tak_dikenali": tak_dikenali,
        "peringkat": peringkat,
    }


def bulan_diketahui(masjid: dict) -> list[tuple[int, int]]:
    """Semua (tahun, bulan) yang ada data ATAU ada output. Diisih menaik."""
    jumpa: set[tuple[int, int]] = set()

    for p in (K.ROOT / "data").glob("*/[0-9][0-9]-*.json"):
        if p.parent.name.isdigit():
            jumpa.add((int(p.parent.name), int(p.name[:2])))

    akar = K.ROOT / masjid["output_root"]
    if akar.exists():
        for p in akar.iterdir():
            m = re.fullmatch(r"(\d{2})-([A-Za-z]+)-(\d{4})", p.name)
            if p.is_dir() and m:
                jumpa.add((int(m.group(3)), int(m.group(1))))

    return sorted(jumpa)


def bulan_seterusnya(diketahui: list[tuple[int, int]]) -> tuple[int, int]:
    """Bulan selepas yang terakhir diketahui (kendalikan lompat tahun)."""
    if not diketahui:
        hari_ini = date.today()
        return hari_ini.year, hari_ini.month
    tahun, bulan = diketahui[-1]
    return (tahun + 1, 1) if bulan == 12 else (tahun, bulan + 1)


def ringkasan(kod_masjid: str | None = None) -> dict:
    """State penuh untuk dashboard."""
    semua = K.senarai_masjid(aktif_sahaja=False)
    masjid = next((m for m in semua if m["kod"] == kod_masjid), None) or semua[0]
    master = K.load_penceramah(masjid)

    diketahui = bulan_diketahui(masjid)
    bulan_list = [status_bulan(masjid, t, b, master) for t, b in diketahui]

    t_next, b_next = bulan_seterusnya(diketahui)
    ada_next = any(s["tahun"] == t_next and s["bulan"] == b_next for s in bulan_list)
    if not ada_next:
        bulan_list.append(status_bulan(masjid, t_next, b_next, master))

    terkini_bulanan = next((s["label"] for s in reversed(bulan_list)
                            if s["bulanan"]["siap"]), None)
    terkini_individu = next((s["label"] for s in reversed(bulan_list)
                             if s["peringkat"] == "selesai"), None)
    belum_siap = [s["label"] for s in bulan_list
                  if s["peringkat"] in ("belum-mula", "separuh")]

    tanpa_gambar = sorted(
        {(k, v["nama_poster"]) for k, v in master.items()
         if not v.get("tile")
         or not (K.ROOT / masjid["ustaz_tile_dir"] / v["tile"]).exists()})

    return {
        "masjid_aktif": masjid,
        "senarai_masjid": semua,
        "bulan": bulan_list,
        "cadang_bulan": {"tahun": t_next, "bulan": b_next,
                         "label": f"{K.BULAN_MS[b_next - 1]} {t_next}"},
        "terkini": {"bulanan": terkini_bulanan, "individu": terkini_individu,
                    "belum_siap": belum_siap},
        "penceramah": {
            "jumlah": len(master),
            "tanpa_gambar": [{"kanon": k, "nama_poster": n}
                             for k, n in tanpa_gambar],
            "tile_dir": str(K.ROOT / masjid["ustaz_tile_dir"]),
        },
        "root": str(K.ROOT),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(ringkasan(sys.argv[1] if len(sys.argv) > 1 else None),
                     ensure_ascii=False, indent=2, default=str))
