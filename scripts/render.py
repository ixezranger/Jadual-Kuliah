#!/usr/bin/env python3
"""
Render jadual kuliah dari JSON ke PNG + PDF.

Guna:
    python scripts/render.py data/2026/08-ogos.json

Output masuk output/<tahun>/<bulan>.png dan .pdf
Skrip GAGAL (exit 1) kalau ada nama ustaz yang tak wujud dalam
data/ustaz-master.json — supaya silap ejaan tak lepas senyap.
"""
import json, sys, os, pathlib, base64, mimetypes
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent

def die(msg):
    print(f"::error::{msg}")
    sys.exit(1)

def data_uri(rel_path):
    """Tukar fail aset jadi data URI supaya render tak bergantung path server."""
    p = ROOT / rel_path
    if not p.exists():
        return None
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"

def font_data_uri(filename="HelveticaNeueLTCom-BdCn.ttf"):
    """Cari font 77 Bold Condensed dalam font-font Windows (per-user atau sistem).
    Tak disimpan dalam repo sebab font berlesen komersial."""
    candidates = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(pathlib.Path(local_appdata) / "Microsoft/Windows/Fonts" / filename)
    candidates.append(pathlib.Path("C:/Windows/Fonts") / filename)
    for c in candidates:
        if c.exists():
            b64 = base64.b64encode(c.read_bytes()).decode()
            return f"data:font/ttf;base64,{b64}"
    return None

def main():
    if len(sys.argv) < 2:
        die("Bagi path fail data. Contoh: python scripts/render.py data/2026/08-ogos.json")

    data_path = ROOT / sys.argv[1]
    if not data_path.exists():
        die(f"Fail data tak jumpa: {data_path}")

    data = json.loads(data_path.read_text(encoding="utf-8"))
    master = json.loads((ROOT / "data/ustaz-master.json").read_text(encoding="utf-8"))
    master = {k: v for k, v in master.items() if not k.startswith("_")}
    master_ustazah = json.loads((ROOT / "data/ustazah-master.json").read_text(encoding="utf-8"))
    master_ustazah = {k: v for k, v in master_ustazah.items() if not k.startswith("_")}

    # ---- SEMAKAN NAMA (automatik) ----
    unknown, missing_photos = [], []
    for hari, info in data["jadual"].items():
        for slot in ("subuh", "maghrib"):
            nama = info.get(slot)
            if not nama:
                continue
            if nama not in master:
                unknown.append((hari, slot, nama))
            else:
                if not (ROOT / "assets/ustaz" / master[nama]).exists():
                    missing_photos.append((nama, f"assets/ustaz/{master[nama]}"))

    for m in data.get("muslimah", []):
        nama = m.get("nama")
        f = master_ustazah.get(nama)
        if not f or not (ROOT / "assets/ustazah" / f).exists():
            missing_photos.append((nama, f"assets/ustazah/{f}" if f else "(tiada dalam ustazah-master.json)"))

    if unknown:
        print("::group::RALAT — nama tak dalam ustaz-master.json")
        for hari, slot, nama in unknown:
            print(f"  Hari {hari} ({slot}): '{nama}'")
        print("::endgroup::")
        die(f"{len(unknown)} nama tak dikenali. Betulkan ejaan atau tambah dalam ustaz-master.json.")

    if missing_photos:
        # amaran je, bukan gagal — placeholder FOTO akan muncul
        print("::warning::Gambar tak jumpa (guna placeholder):")
        for nama, f in missing_photos:
            print(f"  {nama} -> {f}")

    # ---- aset (font header bulan/tahun; header/footer/title dah baked-in base-design) ----
    assets = {
        "font": font_data_uri(),
        "fontLight": font_data_uri("HelveticaNeueLTCom-Lt.ttf"),
    }

    template = (ROOT / "template/jadual.html").read_text(encoding="utf-8")
    inject = (
        "<script>"
        f"window.__DATA__={json.dumps(data, ensure_ascii=False)};"
        f"window.__MASTER__={json.dumps(master, ensure_ascii=False)};"
        f"window.__MASTER_USTAZAH__={json.dumps(master_ustazah, ensure_ascii=False)};"
        f"window.__ASSETS__={json.dumps(assets)};"
        "</script>"
    )
    html = template.replace("<script>\n// Data disuntik", inject + "\n<script>\n// Data disuntik")

    tmp = ROOT / "_render_tmp.html"
    tmp.write_text(html, encoding="utf-8")

    out_dir = ROOT / "output" / str(data["tahun"])
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{sys.argv[1].split('/')[-1].replace('.json','')}"  # cth 08-ogos

    png_path = out_dir / f"{stem}.png"
    pdf_path = out_dir / f"{stem}.pdf"

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width":3000,"height":2025})
        pg.goto("file://" + str(tmp.resolve()))
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        pg.pdf(path=str(pdf_path), width="3000px", height="2025px", print_background=True)
        pg.screenshot(path=str(png_path), full_page=True)
        b.close()

    tmp.unlink(missing_ok=True)
    print(f"✓ Siap: {png_path.relative_to(ROOT)}")
    print(f"✓ Siap: {pdf_path.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
