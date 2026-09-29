#!/usr/bin/env python3
"""
Fungsi kongsi untuk sistem Jadual Kuliah (bulanan + individu).

Tiada pangkalan data — semua state hidup dalam fail JSON bawah data/
dan dalam struktur folder output/.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import pathlib
import re
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent

BULAN_MS = ["Januari", "Februari", "Mac", "April", "Mei", "Jun",
            "Julai", "Ogos", "September", "Oktober", "November", "Disember"]

# Isnin = index 0 mengikut date.weekday()
HARI_MS = ["Isnin", "Selasa", "Rabu", "Khamis", "Jumaat", "Sabtu", "Ahad"]

# Bentuk pendek untuk pil tarikh poster kuliah individu SAHAJA.
# Nama folder output tetap guna nama penuh (lihat nama_folder_bulan).
BULAN_POSTER = {"Januari": "Jan", "Februari": "Feb", "September": "Sept",
                "Oktober": "Okt", "November": "Nov", "Disember": "Dis"}

BULAN_HIJRI = ["Muharram", "Safar", "Rabiulawal", "Rabiulakhir",
               "Jamadilawal", "Jamadilakhir", "Rejab", "Syaaban",
               "Ramadan", "Syawal", "Zulkaedah", "Zulhijjah"]

SLOT_LABEL = {"subuh": "Kuliah Subuh", "maghrib": "Kuliah Maghrib"}

HADIS_DEFAULT = ("Barangsiapa yang menempuh suatu jalan untuk mencari ilmu,\n"
                 "maka Allah memudahkan untuknya jalan menuju ke Syurga.")
HADIS_RIWAYAT_DEFAULT = "(Hadis Riwayat Muslim)"


# --------------------------------------------------------------------------
# Kalendar Hijri
# --------------------------------------------------------------------------
def _takwim_jakim() -> tuple[list[tuple[date, int, int]], list[tuple[date, date]]]:
    """data/hijri-jakim.json -> ([(tarikh_mula, tahunH, bulanH)], [(dari, hingga)])."""
    p = ROOT / "data" / "hijri-jakim.json"
    if not p.exists():
        return [], []
    doc = json.loads(p.read_text(encoding="utf-8"))
    mula = sorted((date.fromisoformat(v), int(k[:4]), int(k[5:]))
                  for k, v in doc.get("mula_bulan", {}).items())
    julat = [(date.fromisoformat(a), date.fromisoformat(b))
             for a, b in doc.get("julat", {}).values()]
    return mula, julat


def gregorian_to_hijri(g: date) -> tuple[int, int, int]:
    """Tukar tarikh Masihi -> (tahun, bulan, hari) Hijri.

    Utamakan takwim rasmi JAKIM (data/hijri-jakim.json, dikemas kini oleh
    scripts/kemas_hijri.py). Di luar julat takwim itu, guna kiraan aritmetik
    yang mungkin tersasar sehari.
    """
    mula, julat = _takwim_jakim()
    if any(a <= g <= b for a, b in julat):
        for tarikh, hy, hm in reversed(mula):
            if tarikh <= g:
                return hy, hm, (g - tarikh).days + 1
    return hijri_aritmetik(g)


def dalam_takwim_jakim(g: date) -> bool:
    return any(a <= g <= b for a, b in _takwim_jakim()[1])


def hijri_aritmetik(g: date) -> tuple[int, int, int]:
    """Algoritma jadual (Kuwaiti) — sandaran bila takwim JAKIM tiada."""
    y, m, d = g.year, g.month, g.day
    if m < 3:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524

    l = jd - 1948440 + 10632
    n = (l - 1) // 10631
    l = l - 10631 * n + 354
    j = (((10985 - l) // 5316) * ((50 * l) // 17719)
         + (l // 5670) * ((43 * l) // 15238))
    l = (l - ((30 - j) // 15) * ((17719 * j) // 50)
         - (j // 16) * ((15238 * j) // 43) + 29)
    hm = (24 * l) // 709
    hd = l - (709 * hm) // 24
    hy = 30 * n + j - 30
    return hy, hm, hd


def hijri_teks(g: date) -> str:
    """'19 Muharram 1448H'"""
    hy, hm, hd = gregorian_to_hijri(g)
    return f"{hd} {BULAN_HIJRI[hm - 1]} {hy}H"


def masihi_teks(g: date) -> str:
    """'5 Julai 2026 (Ahad)' — nama bulan panjang dipendekkan.

    Ruang selamat dalam pil tarikh hanya 486px (antara ikon kalendar dan ikon
    bulan). Enam bulan di bawah terkeluar bila ditulis penuh, jadi dipendekkan.
    Enam yang lain sudah muat dan dibiarkan seperti asal.
    """
    b = BULAN_MS[g.month - 1]
    return f"{g.day} {BULAN_POSTER.get(b, b)} {g.year} ({HARI_MS[g.weekday()]})"


# --------------------------------------------------------------------------
# Nama folder / fail
# --------------------------------------------------------------------------
def nama_folder_bulan(tahun: int, bulan: int) -> str:
    """'08-Ogos-2026'"""
    return f"{bulan:02d}-{BULAN_MS[bulan - 1]}-{tahun}"


_ILLEGAL = re.compile(r'[<>:"/\\|?*]')


def nama_fail_poster(g: date, nama: str, slot: str, tandai_subuh: bool = True) -> str:
    """'2026.08.02 - Ustaz Anas bin Malik.jpg'

    Bila seorang penceramah ada dua slot pada tarikh sama, poster Subuh
    ditanda '(Kuliah Subuh)' — ikut konvensyen folder 07-Julai-2026.
    """
    suffix = " (Kuliah Subuh)" if (slot == "subuh" and tandai_subuh) else ""
    stem = f"{g.year}.{g.month:02d}.{g.day:02d} - {nama}{suffix}"
    return _ILLEGAL.sub("-", stem).strip() + ".jpg"


# --------------------------------------------------------------------------
# Muat data
# --------------------------------------------------------------------------
def load_json(rel: str | pathlib.Path) -> dict:
    p = ROOT / rel if not pathlib.Path(rel).is_absolute() else pathlib.Path(rel)
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(rel: str | pathlib.Path, obj) -> None:
    p = ROOT / rel if not pathlib.Path(rel).is_absolute() else pathlib.Path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")


def senarai_masjid(aktif_sahaja: bool = True) -> list[dict]:
    data = load_json("data/masjid.json")["masjid"]
    return [m for m in data if m.get("aktif", True) or not aktif_sahaja]


def cari_masjid(kod: str) -> dict:
    for m in load_json("data/masjid.json")["masjid"]:
        if m["kod"].upper() == kod.upper():
            return m
    raise KeyError(f"Kod masjid tidak dijumpai: {kod}")


def load_penceramah(masjid: dict) -> dict:
    raw = load_json(masjid.get("penceramah_master", "data/penceramah-master.json"))
    return raw["penceramah"]


def data_uri(rel_path: str | pathlib.Path) -> str:
    """Aset -> data URI supaya render tak bergantung pada path server."""
    p = ROOT / rel_path if not pathlib.Path(rel_path).is_absolute() else pathlib.Path(rel_path)
    if not p.exists():
        raise FileNotFoundError(p)
    mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
