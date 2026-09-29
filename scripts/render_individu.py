#!/usr/bin/env python3
"""
Render poster KULIAH INDIVIDU (Subuh / Maghrib) — 3000 x 1689 px JPG.

Guna:
  # satu poster ujian
  python scripts/render_individu.py --tarikh 2026-08-02 --slot maghrib \
         --penceramah "USTAZ ANAS MALEK"

  # semua poster untuk sebulan, ambil dari jadual bulanan sedia ada
  python scripts/render_individu.py --bulan 2026-08

  # tulis ke folder lain (pratonton/ujian)
  python scripts/render_individu.py --bulan 2026-08 --out-dir _preview

Pilihan berguna:
  --masjid M0001     kod masjid (default: masjid aktif pertama)
  --tajuk "..."      tindih tajuk lalai penceramah
  --dry-run          senarai apa yang akan dijana, tanpa render
  --force            tulis ganti fail yang sudah wujud
"""
from __future__ import annotations

import argparse
import calendar
import io
import json
import pathlib
import sys
from datetime import date

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ki_common as K  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

W, H = 3000, 1689
JPG_QUALITY = 95

FONTS = {
    "__FONT_REGULAR__":        "assets/fonts/poppins/Poppins-Regular.ttf",
    "__FONT_LIGHT__":          "assets/fonts/poppins/Poppins-Light.ttf",
    "__FONT_MEDIUM__":         "assets/fonts/poppins/Poppins-Medium.ttf",
    "__FONT_MEDIUM_ITALIC__":  "assets/fonts/poppins/Poppins-MediumItalic.ttf",
    "__FONT_SEMIBOLD__":       "assets/fonts/poppins/Poppins-SemiBold.ttf",
    "__FONT_SEMIBOLD_ITALIC__": "assets/fonts/poppins/Poppins-SemiBoldItalic.ttf",
}

SPRITE = "assets/base-design/kuliah-individu/ki-base-label.png"
IC_KALENDAR = "assets/base-design/kuliah-individu/logo-kalendar.png"
IC_BULAN = "assets/base-design/kuliah-individu/logo-bulan.png"


def die(msg: str) -> None:
    print(f"::error:: {msg}")
    sys.exit(1)


# --------------------------------------------------------------------------
# Bina senarai kerja
# --------------------------------------------------------------------------
def kerja_dari_bulan(masjid: dict, tahun: int, bulan: int,
                     master: dict) -> tuple[list[dict], list[str]]:
    """Baca jadual bulanan (data/<tahun>/<MM>-<bulan>.json) -> senarai kerja."""
    slug = f"{bulan:02d}-{K.BULAN_MS[bulan - 1].lower()}"
    path = K.ROOT / "data" / str(tahun) / f"{slug}.json"
    if not path.exists():
        die(f"Fail jadual bulanan tak jumpa: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    # Tindihan khusus individu (tajuk per-tarikh), kalau ada.
    ov_path = K.ROOT / "data" / str(tahun) / "individu" / f"{slug}.json"
    overrides = {}
    if ov_path.exists():
        overrides = json.loads(ov_path.read_text(encoding="utf-8")).get("jadual", {})

    kerja, amaran = [], []
    for hari_str, info in sorted(data["jadual"].items(), key=lambda kv: int(kv[0])):
        hari = int(hari_str)
        g = date(tahun, bulan, hari)
        slot_ada = [s for s in ("subuh", "maghrib") if info.get(s)]
        for slot in slot_ada:
            nama_kanon = info[slot]
            p = master.get(nama_kanon)
            if p is None:
                amaran.append(f"{g} {slot}: '{nama_kanon}' tiada dalam "
                              f"data/penceramah-master.json")
                continue
            ov = overrides.get(hari_str, {}).get(slot, {})
            kerja.append({
                "tarikh": g,
                "slot": slot,
                "kanon": nama_kanon,
                "penceramah": p,
                "tajuk": ov.get("tajuk") or p.get("tajuk") or "",
                # tandai '(Kuliah Subuh)' hanya bila hari itu ada dua slot
                "tandai_subuh": len(slot_ada) > 1,
            })
    return kerja, amaran


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------
def deco_untuk(masjid: dict, slot: str) -> tuple[str | None, int, int]:
    """Fail hiasan penjuru kiri-bawah + kedudukannya untuk satu slot.

    Hiasan ini dilukis DI HADAPAN gambar penceramah, jadi ia bertindih sedikit
    dengan bingkai gerbang — seperti reka bentuk rujukan. Pulang (None, 0, 0)
    kalau masjid berkenaan tiada hiasan dikonfigurasi.
    """
    d = (masjid.get("deco") or {}).get(slot)
    if not d or not d.get("fail"):
        return None, 0, 0
    return (f"assets/base-design/kuliah-individu/{d['fail']}",
            int(d.get("x", 0)), int(d.get("bawah", 0)))


def payload_kerja(masjid: dict, kerja: dict) -> dict:
    """Medan teks poster daripada satu baris kerja."""
    p = kerja["penceramah"]
    gelaran = (p.get("gelaran") or "").strip()
    return {
        "nama": f"{gelaran} {p['nama_poster']}".strip(),
        "nama_baris": p.get("nama_baris") or None,
        "tarikh_masihi": K.masihi_teks(kerja["tarikh"]),
        "tarikh_hijri": K.hijri_teks(kerja["tarikh"]),
        "tajuk": kerja["tajuk"],
        "lokasi": masjid["nama_poster"],
        "hadis": K.HADIS_DEFAULT,
        "hadis_riwayat": K.HADIS_RIWAYAT_DEFAULT,
        "deco_x": deco_untuk(masjid, kerja["slot"])[1],
        "deco_bawah": deco_untuk(masjid, kerja["slot"])[2],
    }


def bina_html(templat: str, payload: dict, aset: dict) -> str:
    """Suntik font (data URI), aset dan payload ke dalam templat."""
    html = templat
    for token, path in FONTS.items():
        html = html.replace(token, K.data_uri(path))
    for token, uri in aset.items():
        html = html.replace(token, uri)
    return html.replace(
        "</head>",
        "<script>window.KI=" + json.dumps(payload, ensure_ascii=False)
        + ";</script></head>", 1)


def html_untuk_pratonton(bg_rel: str, tile_rel: str, payload: dict,
                         deco_rel: str | None = None) -> str:
    """HTML lengkap (semua aset terbenam) — untuk pratonton dalam iframe."""
    templat = (K.ROOT / "template" / "kuliah-individu.html").read_text(encoding="utf-8")
    return bina_html(templat, payload, {
        "__BG__": K.data_uri(bg_rel),
        "__TILE__": K.data_uri(tile_rel),
        "__DECO__": K.data_uri(deco_rel) if deco_rel else "",
        "__SPRITE__": K.data_uri(SPRITE),
        "__IC_KALENDAR__": K.data_uri(IC_KALENDAR),
        "__IC_BULAN__": K.data_uri(IC_BULAN),
    })


def render_html(html: str, out_path: pathlib.Path) -> pathlib.Path:
    """Satu render sekali-guna (guna oleh alat manual)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H},
                                device_scale_factor=1)
        page.set_content(html, wait_until="load")
        page.wait_for_selector("html[data-ki-ready='1']", timeout=30000)
        page.evaluate("document.fonts.ready")
        png = page.screenshot(type="png",
                              clip={"x": 0, "y": 0, "width": W, "height": H})
        browser.close()
    img = Image.open(io.BytesIO(png)).convert("RGB")
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
    img.save(out_path, "JPEG", quality=JPG_QUALITY, subsampling=0, optimize=True)
    return out_path


def render_semua(masjid: dict, senarai: list[dict], out_dir: pathlib.Path,
                 force: bool) -> list[pathlib.Path]:
    templat = (K.ROOT / "template" / "kuliah-individu.html").read_text(encoding="utf-8")

    # Aset yang sama untuk semua poster — encode sekali sahaja.
    aset_tetap = {
        "__SPRITE__": K.data_uri(SPRITE),
        "__IC_KALENDAR__": K.data_uri(IC_KALENDAR),
        "__IC_BULAN__": K.data_uri(IC_BULAN),
    }
    bg_cache: dict[str, str] = {}
    tile_cache: dict[str, str] = {}
    deco_cache: dict[str, str] = {}

    out_dir.mkdir(parents=True, exist_ok=True)
    hasil: list[pathlib.Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H},
                                device_scale_factor=1)
        for kerja in senarai:
            p = kerja["penceramah"]
            slot = kerja["slot"]

            out_name = K.nama_fail_poster(
                kerja["tarikh"],
                p.get("nama_fail") or p["nama_poster"],
                slot,
                kerja.get("tandai_subuh", False))
            out_path = out_dir / out_name
            if out_path.exists() and not force:
                print(f"  · langkau (sudah ada): {out_name}")
                continue

            bg_rel = ("assets/base-design/kuliah-individu/"
                      + masjid["background"][slot])
            if bg_rel not in bg_cache:
                bg_cache[bg_rel] = K.data_uri(bg_rel)

            tile_rel = f"{masjid['ustaz_tile_dir']}/{p['tile']}"
            if tile_rel not in tile_cache:
                tile_cache[tile_rel] = K.data_uri(tile_rel)

            deco_rel, _, _ = deco_untuk(masjid, slot)
            if deco_rel and deco_rel not in deco_cache:
                deco_cache[deco_rel] = K.data_uri(deco_rel)

            aset = dict(aset_tetap,
                        __BG__=bg_cache[bg_rel],
                        __TILE__=tile_cache[tile_rel],
                        __DECO__=deco_cache.get(deco_rel, ""))

            page.set_content(
                bina_html(templat, payload_kerja(masjid, kerja), aset),
                wait_until="load")
            page.wait_for_selector("html[data-ki-ready='1']", timeout=30000)
            page.evaluate("document.fonts.ready")

            png = page.screenshot(type="png", clip={"x": 0, "y": 0,
                                                    "width": W, "height": H})
            img = Image.open(io.BytesIO(png)).convert("RGB")
            if img.size != (W, H):
                img = img.resize((W, H), Image.LANCZOS)
            img.save(out_path, "JPEG", quality=JPG_QUALITY,
                     subsampling=0, optimize=True)
            print(f"  ✓ {out_name}")
            hasil.append(out_path)

        browser.close()
    return hasil


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Render poster Kuliah Individu.")
    ap.add_argument("--masjid", default=None, help="Kod masjid, cth M0001")
    ap.add_argument("--bulan", help="YYYY-MM — render satu bulan penuh")
    ap.add_argument("--tarikh", help="YYYY-MM-DD — render satu poster")
    ap.add_argument("--slot", choices=["subuh", "maghrib"], default="maghrib")
    ap.add_argument("--penceramah", help="Kunci kanonikal, cth 'USTAZ ANAS MALEK'")
    ap.add_argument("--tajuk", help="Tindih tajuk lalai")
    ap.add_argument("--out-dir", help="Folder output (default: ikut konvensyen)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--json", action="store_true",
                    help="Keluarkan ringkasan JSON (untuk dashboard)")
    args = ap.parse_args()

    masjid = (K.cari_masjid(args.masjid) if args.masjid
              else K.senarai_masjid()[0])
    master = K.load_penceramah(masjid)

    amaran: list[str] = []
    if args.bulan:
        try:
            tahun, bulan = (int(x) for x in args.bulan.split("-"))
        except ValueError:
            die("--bulan mesti format YYYY-MM")
        senarai, amaran = kerja_dari_bulan(masjid, tahun, bulan, master)
        default_out = (K.ROOT / masjid["output_root"]
                       / K.nama_folder_bulan(tahun, bulan))
    elif args.tarikh and args.penceramah:
        g = date.fromisoformat(args.tarikh)
        p = master.get(args.penceramah)
        if p is None:
            die(f"'{args.penceramah}' tiada dalam data/penceramah-master.json")
        senarai = [{"tarikh": g, "slot": args.slot, "kanon": args.penceramah,
                    "penceramah": p,
                    "tajuk": args.tajuk or p.get("tajuk") or "",
                    "tandai_subuh": False}]
        default_out = (K.ROOT / masjid["output_root"]
                       / K.nama_folder_bulan(g.year, g.month))
    else:
        die("Bagi --bulan YYYY-MM, atau --tarikh + --penceramah.")

    out_dir = (K.ROOT / args.out_dir) if args.out_dir else default_out

    # Semakan gambar penceramah — ini yang dashboard papar sebagai 'perlu tindakan'.
    tiada_gambar = []
    boleh_render = []
    for k in senarai:
        p = k["penceramah"]
        tile = p.get("tile")
        ada = bool(tile) and (K.ROOT / masjid["ustaz_tile_dir"] / tile).exists()
        if ada:
            boleh_render.append(k)
        else:
            tiada_gambar.append({
                "tarikh": k["tarikh"].isoformat(),
                "slot": k["slot"],
                "kanon": k["kanon"],
                "nama_poster": p["nama_poster"],
                "perlu_fail": (f"{masjid['ustaz_tile_dir']}/"
                               f"ki-{p['nama_poster'].replace(' ', '-')}.png"),
            })

    for w in amaran:
        print(f"  ! {w}")
    if tiada_gambar:
        print(f"\n  ! {len(tiada_gambar)} penceramah tiada gambar berbingkai "
              f"— poster berkenaan DILANGKAU:")
        for t in tiada_gambar:
            print(f"      {t['tarikh']} {t['slot']:8s} {t['nama_poster']}")
        print(f"    Sediakan fail PNG dalam {masjid['ustaz_tile_dir']}/ "
              f"dan kemas kini 'tile' dalam data/penceramah-master.json.\n")

    print(f"Masjid : {masjid['kod']} — {masjid['nama']}")
    print(f"Output : {out_dir}")
    print(f"Poster : {len(boleh_render)} sedia, {len(tiada_gambar)} tertangguh\n")

    dijana = []
    if args.dry_run:
        for k in boleh_render:
            p = k["penceramah"]
            print("  · " + K.nama_fail_poster(
                k["tarikh"], p.get("nama_fail") or p["nama_poster"],
                k["slot"], k.get("tandai_subuh", False)))
    elif boleh_render:
        dijana = render_semua(masjid, boleh_render, out_dir, args.force)

    if args.json:
        print("\n__JSON__" + json.dumps({
            "masjid": masjid["kod"],
            "out_dir": str(out_dir),
            "dijana": [p.name for p in dijana],
            "tertangguh": tiada_gambar,
            "amaran": amaran,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
