#!/usr/bin/env python3
"""
Pelayan tempatan untuk Papan Kawalan Jadual Kuliah.

  python scripts/serve_dashboard.py          -> http://127.0.0.1:8765

Guna http.server dari pustaka standard sahaja — tiada pemasangan tambahan,
tiada pangkalan data. Semua state disimpan sebagai fail JSON dalam data/.

Pelayan ini HANYA untuk kegunaan tempatan (127.0.0.1) — tiada pengesahan.
"""
from __future__ import annotations

import calendar
import json
import mimetypes
import os
import pathlib
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import buat_bulan as BB  # noqa: E402
import dashboard_state as S  # noqa: E402
import ki_common as K  # noqa: E402
import render_individu as RI  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PORT = int(os.environ.get("KI_PORT", "8765"))
DASH = K.ROOT / "dashboard"

# job_id -> {"status", "log": [str], "mula", "tamat"}
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


# --------------------------------------------------------------------------
# Kerja latar belakang
# --------------------------------------------------------------------------
def jalankan_job(job_id: str, arahan: list[str]) -> None:
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "berjalan"
    try:
        proc = subprocess.Popen(
            arahan, cwd=str(K.ROOT), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1)
        for baris in proc.stdout:
            with JOBS_LOCK:
                JOBS[job_id]["log"].append(baris.rstrip("\n"))
        kod = proc.wait()
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "selesai" if kod == 0 else "gagal"
            JOBS[job_id]["kod"] = kod
    except Exception as e:  # noqa: BLE001
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "gagal"
            JOBS[job_id]["log"].append(f"RALAT: {e}")
    finally:
        with JOBS_LOCK:
            JOBS[job_id]["tamat"] = time.time()


def mula_job(arahan: list[str]) -> str:
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "menunggu", "log": [],
                        "mula": time.time(), "tamat": None,
                        "arahan": " ".join(arahan)}
    threading.Thread(target=jalankan_job, args=(job_id, arahan),
                     daemon=True).start()
    return job_id


def urai_multipart(badan: bytes, ctype: str) -> dict[str, tuple[str | None, bytes]]:
    """Penghurai multipart/form-data minimum.

    Ganti modul `cgi` (dibuang dalam Python 3.13). Pulangkan
    {nama_medan: (nama_fail_atau_None, kandungan_bait)}.
    """
    tanda = None
    for bhg in ctype.split(";"):
        bhg = bhg.strip()
        if bhg.startswith("boundary="):
            tanda = bhg[len("boundary="):].strip('"')
    if not tanda:
        return {}

    pemisah = b"--" + tanda.encode()
    keluar: dict[str, tuple[str | None, bytes]] = {}
    for blok in badan.split(pemisah):
        if blok in (b"", b"--", b"--\r\n") or b"\r\n\r\n" not in blok:
            continue
        mentah_kepala, _, kandungan = blok.partition(b"\r\n\r\n")
        kandungan = kandungan[:-2] if kandungan.endswith(b"\r\n") else kandungan

        nama = nama_fail = None
        for baris in mentah_kepala.decode("utf-8", "replace").splitlines():
            if baris.lower().startswith("content-disposition:"):
                for bhg in baris.split(";")[1:]:
                    kunci, _, nilai = bhg.strip().partition("=")
                    nilai = nilai.strip('"')
                    if kunci == "name":
                        nama = nilai
                    elif kunci == "filename":
                        nama_fail = nilai
        if nama:
            keluar[nama] = (nama_fail, kandungan)
    return keluar


def buka_folder(path: str) -> bool:
    p = pathlib.Path(path)
    if not p.exists():
        p = p.parent
    if not p.exists():
        return False
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(p))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return True
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# Sediakan data jadual daripada imej AJK
#
# Borang dashboard -> teks mentah (format jadual-mentah.txt) -> buat_bulan.py.
# Padanan ejaan nama, corak Khamis/Ahad dan format JSON kekal di buat_bulan,
# jadi hasilnya SAMA seperti menjalankan skrip itu dari terminal.
# --------------------------------------------------------------------------
IMEJ_SUMBER = {".png", ".jpg", ".jpeg", ".webp"}


def _laluan_bulan(tahun: int, bulan: int) -> tuple[str, pathlib.Path, pathlib.Path]:
    slug = S.bulan_slug(bulan)
    return (slug, K.ROOT / "input" / str(tahun) / slug,
            K.ROOT / "data" / str(tahun) / f"{slug}.json")


def _hari_nama(tahun: int, bulan: int, h: int) -> str:
    return K.HARI_MS[date(tahun, bulan, h).weekday()]


def _baris_dari_data(data: dict) -> tuple[dict, list]:
    """Fail JSON sedia ada -> baris borang (supaya boleh diubah & dijana semula)."""
    hari = {}
    for h_str, v in data.get("jadual", {}).items():
        h = int(h_str)
        if "event" in v:
            if v["event"] == BB.TEKS_YASIN:
                hari[h] = {"jenis": "yasin"}
            else:
                hari[h] = {"jenis": "acara", "acara": v["event"].replace("\n", " ")}
        else:
            hari[h] = {"jenis": "kuliah", "subuh": v.get("subuh", ""),
                       "maghrib": v.get("maghrib", "")}
    muslimat = []
    for m in data.get("muslimah", []):
        no = re.match(r"\s*(\d{1,2})", m.get("tarikh", ""))
        muslimat.append({"hari": int(no.group(1)) if no else "",
                         "jam": m.get("jam", ""), "nama": m.get("nama", "")})
    return hari, muslimat


def _baris_dari_mentah(teks: str) -> tuple[dict, list]:
    jadual, mus = BB.baca_mentah_teks(teks)
    hari = {}
    for h, v in jadual.items():
        if "event" in v:
            hari[h] = ({"jenis": "yasin"} if v["event"] == BB.TEKS_YASIN
                       else {"jenis": "acara", "acara": v["event"]})
        else:
            hari[h] = {"jenis": "kuliah", "subuh": v.get("subuh", ""),
                       "maghrib": v.get("maghrib", "")}
    return hari, [{"hari": h, "jam": j, "nama": n} for h, j, n in mus]


def borang_mentah(tahun: int, bulan: int) -> dict:
    """Keadaan awal borang: dari JSON sedia ada, atau jadual-mentah.txt, atau kosong."""
    slug, input_dir, data_path = _laluan_bulan(tahun, bulan)
    mentah_path = input_dir / "jadual-mentah.txt"
    akhir = calendar.monthrange(tahun, bulan)[1]

    asal, hari, muslimat = "baharu", {}, []
    if data_path.exists():
        asal = "data"
        hari, muslimat = _baris_dari_data(K.load_json(data_path))
    elif mentah_path.exists():
        asal = "mentah"
        try:
            hari, muslimat = _baris_dari_mentah(mentah_path.read_text(encoding="utf-8"))
        except SystemExit:
            asal = "baharu"

    baris = []
    for h in range(1, akhir + 1):
        nama_hari = _hari_nama(tahun, bulan, h)
        lalai = ({"jenis": "yasin"} if nama_hari == "Khamis"
                 else {"jenis": "kuliah"})
        r = {"jenis": "kuliah", "subuh": "", "maghrib": "", "acara": ""}
        r.update(hari.get(h) or lalai)
        r.update({"hari": h, "nama_hari": nama_hari})
        baris.append(r)

    penceramah, _, ustazah = BB.muat_registry()
    sumber = sorted(p for p in input_dir.glob("*")
                    if p.suffix.lower() in IMEJ_SUMBER) if input_dir.exists() else []
    gambar_bulanan = sorted((p.name for p in (K.ROOT / "assets/ustaz").glob("*.png")),
                            key=str.lower)
    return {
        "tahun": tahun, "bulan": bulan, "slug": slug,
        "label": f"{K.BULAN_MS[bulan - 1]} {tahun}",
        "asal": asal,
        "ada_data": data_path.exists(),
        "fail_data": f"data/{tahun}/{slug}.json",
        "sumber": [p.relative_to(K.ROOT).as_posix() for p in sumber],
        "hari": baris,
        "muslimat": muslimat,
        "penceramah": sorted(penceramah),
        "ustazah": sorted(ustazah),
        "gambar_bulanan": gambar_bulanan,
    }


def daftar_penceramah(b: dict) -> tuple[int, dict]:
    """Penceramah baharu -> penceramah-master.json (poster individu)
    DAN ustaz-master.json (jadual bulanan). render.py gagal jika nama
    dalam jadual tiada dalam ustaz-master, jadi kedua-duanya wajib."""
    kanon = " ".join((b.get("kanon") or "").upper().split())
    if not BB.token(kanon):
        return 400, {"ralat": "Nama standard diperlukan"}

    pm = K.load_json("data/penceramah-master.json")
    um_path = K.ROOT / "data/ustaz-master.json"
    um = json.loads(um_path.read_text(encoding="utf-8"))

    for n in [*pm["penceramah"], *(k for k in um if not k.startswith("_"))]:
        if n == kanon or BB.kunci(n) == BB.kunci(kanon):
            return 409, {"ralat": f"Sudah wujud dalam rekod sebagai '{n}'", "nama": n}

    tile = (b.get("tile") or "").strip() or None
    fail_bulanan = pathlib.Path((b.get("gambar_bulanan") or "").strip()).name
    if not fail_bulanan:
        return 400, {"ralat": "Nama fail gambar jadual bulanan diperlukan"}
    if not fail_bulanan.lower().endswith(".png"):
        fail_bulanan += ".png"

    nama_poster = " ".join((b.get("nama_poster") or kanon.title()).split())
    pm["penceramah"][kanon] = {
        "gelaran": b.get("gelaran", "YBhg Al-Fadhil"),
        "nama_poster": nama_poster,
        "nama_fail": nama_poster,
        "tile": tile,
        "tajuk": (b.get("tajuk") or "").strip(),
        "nama_baris": None,
    }
    K.save_json("data/penceramah-master.json", pm)

    # Tambah di hujung tanpa menyusun semula fail (kekalkan gaya & baris kosong).
    teks = um_path.read_text(encoding="utf-8").rstrip()
    if not teks.endswith("}"):
        return 500, {"ralat": "Format ustaz-master.json tidak dijangka"}
    entri = f"  {json.dumps(kanon, ensure_ascii=False)}: {json.dumps(fail_bulanan, ensure_ascii=False)}"
    teks = teks[:-1].rstrip() + ",\n" + entri + "\n}\n"
    json.loads(teks)  # pastikan masih JSON sah sebelum menulis
    um_path.write_text(teks, encoding="utf-8")

    return 200, {"ok": True, "kanon": kanon, "gambar_bulanan": fail_bulanan,
                 "gambar_ada": (K.ROOT / "assets/ustaz" / fail_bulanan).exists()}


def _bersih(s) -> str:
    # '|' ialah pemisah dalam format mentah; baris baharu memecah format.
    return " ".join(str(s or "").replace("|", " ").split())


def jadi_mentah(tahun: int, bulan: int, hari: list[dict],
                muslimat: list[dict], sumber: list[str]) -> str:
    """Baris borang -> teks format jadual-mentah.txt."""
    b = ["// Dijana daripada borang dashboard (Isi & jana JSON).",
         *[f"//   {pathlib.Path(s).name}" for s in sumber],
         f"// {BB.BULAN_MS[bulan - 1]} {tahun}", ""]
    for r in sorted(hari, key=lambda r: int(r["hari"])):
        h, jenis = int(r["hari"]), r.get("jenis")
        if jenis == "yasin":
            b.append(f"{h:<3} #yasin")
        elif jenis == "acara":
            b.append(f"{h:<3} #event {_bersih(r.get('acara'))}".rstrip())
        else:
            subuh, maghrib = _bersih(r.get("subuh")), _bersih(r.get("maghrib"))
            # Ahad sentiasa dua slot (sama seperti corak lalai buat_bulan).
            ahad = date(tahun, bulan, h).weekday() == BB.AHAD
            if subuh or (ahad and maghrib):
                b.append(f"{h:<3} {subuh} | {maghrib}".rstrip())
            else:
                b.append(f"{h:<3} {maghrib}".rstrip())

    mus = [m for m in muslimat if str(m.get("hari", "")).strip() and _bersih(m.get("nama"))]
    if mus:
        b += ["", "[muslimat]"]
        for m in mus:
            b.append(f"{int(m['hari']):<2} | {_bersih(m.get('jam'))} | {_bersih(m['nama'])}")
    return "\n".join(b) + "\n"


def ingatan_padanan(penceramah: list[str]) -> dict[str, str]:
    """Ejaan mentah yang sudah pernah disahkan pada bulan-bulan lepas.

    Setiap bulan yang ada jadual-mentah.txt DAN fail data dipasangkan ikut
    tarikh/slot: ejaan dalam imej AJK -> nama standard yang akhirnya dipakai.
    Jadi 'UST.LUTFFI' yang disahkan sebagai USTAZ LUTFI ISMAIL pada September
    terus dikenali pada bulan-bulan seterusnya.
    """
    ingat: dict[str, str] = {}
    sah = set(penceramah)
    for mp in sorted((K.ROOT / "input").glob("*/*/jadual-mentah.txt")):
        dp = K.ROOT / "data" / mp.parent.parent.name / f"{mp.parent.name}.json"
        if not dp.exists():
            continue
        try:
            mentah_jadual, _ = BB.baca_mentah_teks(mp.read_text(encoding="utf-8"))
            data = K.load_json(dp).get("jadual", {})
        except (SystemExit, ValueError):
            continue
        for h, v in mentah_jadual.items():
            for slot in ("subuh", "maghrib"):
                asal, akhir = v.get(slot), data.get(str(h), {}).get(slot)
                if asal and akhir in sah and BB.kunci(asal):
                    ingat[BB.kunci(asal)] = akhir
    return ingat


def proses_mentah(b: dict) -> tuple[int, dict]:
    """Semak (dan jika diminta, tulis) jadual daripada borang."""
    try:
        tahun, bulan = (int(x) for x in (b.get("bulan") or "").split("-"))
    except ValueError:
        return 400, {"ralat": "bulan (YYYY-MM) diperlukan"}

    slug, input_dir, data_path = _laluan_bulan(tahun, bulan)
    sumber = [p.name for p in input_dir.glob("*")
              if p.suffix.lower() in IMEJ_SUMBER] if input_dir.exists() else []
    teks = jadi_mentah(tahun, bulan, b.get("hari") or [], b.get("muslimat") or [], sumber)

    penceramah, ustaz, ustazah = BB.muat_registry()
    try:
        mj, mm = BB.baca_mentah_teks(teks)
        doc, laporan = BB.bina(tahun, bulan, mj, mm, penceramah, ustazah)
    except SystemExit as e:
        return 400, {"ralat": str(e)}
    except ValueError as e:  # cth tarikh muslimat di luar bulan
        return 400, {"ralat": f"tarikh tidak sah: {e}"}

    s = BB.semakan(doc, laporan, ustaz)

    # Padanan untuk SETIAP nama yang diisi (termasuk yang tepat), supaya
    # borang boleh menggantikan ejaan mentah dengan nama standard.
    def padan(mentah_nama: str, senarai: list[str], ingat: dict | None = None) -> dict:
        nama, skor, tahap = BB.padan(mentah_nama, senarai)
        if tahap != "tepat" and ingat and BB.kunci(mentah_nama) in ingat:
            # pernah disahkan pada bulan lepas — lebih dipercayai daripada teka
            return {"tahap": "auto", "nama": ingat[BB.kunci(mentah_nama)],
                    "skor": 1.0, "sumber": "bulan lepas"}
        return {"tahap": tahap, "nama": nama, "skor": round(skor, 2)}

    ingat = ingatan_padanan(penceramah)
    padanan = {}
    for r in b.get("hari") or []:
        if r.get("jenis", "kuliah") != "kuliah":
            continue
        for slot in ("subuh", "maghrib"):
            if _bersih(r.get(slot)):
                padanan[f"{r['hari']}|{slot}"] = padan(_bersih(r[slot]), penceramah, ingat)
    for m in b.get("muslimat") or []:
        if str(m.get("hari", "")).strip() and _bersih(m.get("nama")):
            padanan[f"{m['hari']}|muslimah"] = padan(_bersih(m["nama"]), sorted(ustazah))

    hasil = {
        "padanan": padanan,
        "isu": {k: len(v) for k, v in s.items()},
        "hilang": s["hilang"],
        "fail_data": f"data/{tahun}/{slug}.json",
        "ditulis": False,
    }
    if not b.get("tulis"):
        return 200, hasil

    if data_path.exists() and not b.get("ganti"):
        return 409, {"ralat": f"{data_path.name} sudah wujud", "wujud": True}

    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "jadual-mentah.txt").write_text(teks, encoding="utf-8")
    data_path.parent.mkdir(parents=True, exist_ok=True)
    if data_path.exists():
        # Salinan keselamatan — suntingan slot terdahulu masih boleh dirujuk.
        data_path.with_suffix(".json.bak").write_bytes(data_path.read_bytes())
    data_path.write_text(BB.jadi_teks(doc), encoding="utf-8")
    hasil["ditulis"] = True
    return 200, hasil


# --------------------------------------------------------------------------
def dalam_root(p: pathlib.Path) -> bool:
    """Halang path traversal — hadkan capaian kepada folder projek."""
    try:
        p.resolve().relative_to(K.ROOT.resolve())
        return True
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "JadualKuliah/1.0"

    # ---------------------------------------------------------------- util
    def _hantar(self, kod: int, badan: bytes, mime: str = "application/json",
                cache: bool = False) -> None:
        self.send_response(kod)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(badan)))
        if not cache:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(badan)

    def _json(self, obj, kod: int = 200) -> None:
        self._hantar(kod, json.dumps(obj, ensure_ascii=False,
                                     default=str).encode("utf-8"))

    def _badan_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def log_message(self, fmt, *args):  # senyapkan log akses
        pass

    # ---------------------------------------------------------------- GET
    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        laluan = unquote(u.path)

        if laluan in ("/", "/index.html"):
            return self._fail_statik(DASH / "index.html")

        if laluan.startswith("/dashboard/"):
            return self._fail_statik(DASH / laluan[len("/dashboard/"):])

        if laluan == "/api/state":
            return self._json(S.ringkasan(q.get("masjid", [None])[0]))

        if laluan.startswith("/api/job/"):
            job_id = laluan.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            return self._json(job or {"status": "tiada"},
                              200 if job else 404)

        if laluan == "/api/penceramah":
            return self._json(K.load_json("data/penceramah-master.json"))

        if laluan == "/api/gambar":
            kod = (q.get("masjid") or [None])[0]
            m = K.cari_masjid(kod) if kod else K.senarai_masjid()[0]
            folder = K.ROOT / m["ustaz_tile_dir"]
            # tile -> siapa yang sudah menggunakannya
            guna = {v["tile"]: kanon
                    for kanon, v in K.load_penceramah(m).items() if v.get("tile")}
            fail = sorted((p.name for p in folder.glob("*.png")), key=str.lower)
            return self._json({
                "dir": m["ustaz_tile_dir"],
                "fail": [{"nama": f, "guna": guna.get(f)} for f in fail],
            })

        if laluan == "/api/mentah":
            try:
                tahun, bulan = (int(x) for x in q["bulan"][0].split("-"))
            except (KeyError, ValueError):
                return self._json({"ralat": "bulan (YYYY-MM) diperlukan"}, 400)
            return self._json(borang_mentah(tahun, bulan))

        if laluan == "/api/tarikh":
            g = date.fromisoformat(q["tarikh"][0])
            return self._json({"masihi": K.masihi_teks(g),
                               "hijri": K.hijri_teks(g)})

        # Sajikan fail dalam projek (pratonton poster / imej sumber).
        if laluan == "/fail":
            p = pathlib.Path(q.get("path", [""])[0])
            if not p.is_absolute():
                p = K.ROOT / p
            if not dalam_root(p) or not p.is_file():
                return self._json({"ralat": "tidak dibenarkan"}, 403)
            mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
            return self._hantar(200, p.read_bytes(), mime, cache=True)

        return self._json({"ralat": "tiada"}, 404)

    def _fail_statik(self, p: pathlib.Path) -> None:
        if not dalam_root(p) or not p.is_file():
            return self._json({"ralat": "tiada"}, 404)
        mime = mimetypes.guess_type(str(p))[0] or "text/plain"
        if mime.startswith("text/") or mime in ("application/javascript",):
            mime += "; charset=utf-8"
        self._hantar(200, p.read_bytes(), mime)

    # ---------------------------------------------------------------- POST
    def do_POST(self):  # noqa: N802
        laluan = unquote(urlparse(self.path).path)

        if laluan == "/api/generate":
            return self._jana()
        if laluan == "/api/upload":
            return self._muat_naik()
        if laluan == "/api/buka-folder":
            b = self._badan_json()
            ok = buka_folder(b.get("path", ""))
            return self._json({"ok": ok})
        if laluan == "/api/masjid":
            return self._tambah_masjid()
        if laluan == "/api/penceramah":
            return self._simpan_penceramah()
        if laluan == "/api/jadual":
            return self._simpan_jadual()
        if laluan == "/api/mentah":
            kod, hasil = proses_mentah(self._badan_json())
            return self._json(hasil, kod)
        if laluan == "/api/penceramah-baru":
            kod, hasil = daftar_penceramah(self._badan_json())
            return self._json(hasil, kod)
        if laluan == "/api/template":
            return self._templat_pratonton()
        if laluan == "/api/render-manual":
            return self._render_manual()

        return self._json({"ralat": "tiada"}, 404)

    # ------------------------------------------------------- alat manual
    @staticmethod
    def _sediakan_manual(b: dict) -> tuple[dict, str, str, dict, str | None]:
        """Sahkan muatan manual -> (masjid, bg_rel, tile_rel, payload)."""
        masjid = K.cari_masjid(b.get("masjid") or "M0001")
        slot = b.get("slot", "maghrib")
        if slot not in ("subuh", "maghrib"):
            raise ValueError("slot mesti 'subuh' atau 'maghrib'")

        master = K.load_penceramah(masjid)
        p = master.get(b.get("kanon") or "")
        if p is None:
            raise ValueError("penceramah tidak dijumpai dalam registry")
        if not p.get("tile"):
            raise ValueError(f"{p['nama_poster']} belum ada gambar berbingkai")

        bg_rel = "assets/base-design/kuliah-individu/" + masjid["background"][slot]
        tile_rel = f"{masjid['ustaz_tile_dir']}/{p['tile']}"
        for rel in (bg_rel, tile_rel):
            if not (K.ROOT / rel).exists():
                raise ValueError(f"aset tiada: {rel}")

        baris = [s for s in (b.get("nama_baris") or []) if s.strip()]
        payload = {
            "nama": " ".join(baris),
            "nama_baris": baris or None,
            "tarikh_masihi": b.get("tarikh_masihi", ""),
            "tarikh_hijri": b.get("tarikh_hijri", ""),
            "tajuk": b.get("tajuk", ""),
            "lokasi": b.get("lokasi", masjid["nama_poster"]),
            "hadis": b.get("hadis", K.HADIS_DEFAULT),
            "hadis_riwayat": b.get("hadis_riwayat", K.HADIS_RIWAYAT_DEFAULT),
        }

        # Hiasan penjuru — sama seperti penjanaan pukal, supaya poster manual
        # tidak terpesong daripada yang dijana secara pukal.
        deco_rel, deco_x, deco_bawah = RI.deco_untuk(masjid, slot)
        payload["deco_x"] = deco_x
        payload["deco_bawah"] = deco_bawah
        return masjid, bg_rel, tile_rel, payload, deco_rel

    def _templat_pratonton(self) -> None:
        try:
            _, bg, tile, payload, deco = self._sediakan_manual(self._badan_json())
        except (ValueError, KeyError) as e:
            return self._json({"ralat": str(e)}, 400)
        html = RI.html_untuk_pratonton(bg, tile, payload, deco)
        return self._hantar(200, html.encode("utf-8"), "text/html; charset=utf-8")

    def _render_manual(self) -> None:
        b = self._badan_json()
        try:
            masjid, bg, tile, payload, deco = self._sediakan_manual(b)
        except (ValueError, KeyError) as e:
            return self._json({"ralat": str(e)}, 400)

        nama_fail = pathlib.Path((b.get("fail") or "poster.jpg")
                                 .replace("\\", "/")).name
        if not nama_fail.lower().endswith(".jpg"):
            nama_fail += ".jpg"

        g = date.fromisoformat(b["tarikh"]) if b.get("tarikh") else date.today()
        out_dir = (K.ROOT / masjid["output_root"]
                   / K.nama_folder_bulan(g.year, g.month))

        try:
            hasil = RI.render_html(RI.html_untuk_pratonton(bg, tile, payload, deco),
                                   out_dir / nama_fail)
        except Exception as e:  # noqa: BLE001
            return self._json({"ralat": f"render gagal: {e}"}, 500)
        return self._json({"ok": True, "path": str(hasil)})

    # ------------------------------------------------------------ tindakan
    def _jana(self) -> None:
        b = self._badan_json()
        jenis = b.get("jenis")
        tahun, bulan = int(b["tahun"]), int(b["bulan"])
        py = sys.executable

        if jenis == "individu":
            arahan = [py, "scripts/render_individu.py",
                      "--masjid", b.get("masjid", "M0001"),
                      "--bulan", f"{tahun}-{bulan:02d}"]
            if b.get("force"):
                arahan.append("--force")
        elif jenis == "bulanan":
            arahan = [py, "scripts/render.py",
                      f"data/{tahun}/{S.bulan_slug(bulan)}.json"]
        else:
            return self._json({"ralat": "jenis tidak sah"}, 400)

        return self._json({"job": mula_job(arahan)})

    def _muat_naik(self) -> None:
        ctype = self.headers.get("Content-Type", "")
        if not ctype.startswith("multipart/form-data"):
            return self._json({"ralat": "perlu multipart/form-data"}, 400)

        n = int(self.headers.get("Content-Length") or 0)
        medan = urai_multipart(self.rfile.read(n), ctype)

        tahun = int(medan["tahun"][1].decode())
        bulan = int(medan["bulan"][1].decode())
        folder = K.ROOT / "input" / str(tahun) / S.bulan_slug(bulan)
        folder.mkdir(parents=True, exist_ok=True)

        nama_fail, kandungan = medan.get("fail", (None, b""))
        if not nama_fail or not kandungan:
            return self._json({"ralat": "tiada fail"}, 400)

        nama = pathlib.Path(nama_fail.replace("\\", "/")).name  # buang path
        sasaran = folder / nama
        if sasaran.exists():                              # jangan tulis ganti
            sasaran = folder / f"{sasaran.stem}-{int(time.time())}{sasaran.suffix}"
        sasaran.write_bytes(kandungan)
        return self._json({"ok": True, "fail": sasaran.name,
                           "folder": str(folder)})

    def _tambah_masjid(self) -> None:
        b = self._badan_json()
        kod = (b.get("kod") or "").strip().upper()
        if not kod:
            return self._json({"ralat": "kod diperlukan"}, 400)

        fail = K.load_json("data/masjid.json")
        if any(m["kod"].upper() == kod for m in fail["masjid"]):
            return self._json({"ralat": f"{kod} sudah wujud"}, 409)

        fail["masjid"].append({
            "kod": kod,
            "nama": b.get("nama", kod),
            "nama_poster": b.get("nama_poster", b.get("nama", kod)),
            "aktif": True,
            "background": {
                "subuh": b.get("bg_subuh",
                               f"Background-Design-Kuliah-Subuh-01-{kod}.png"),
                "maghrib": b.get("bg_maghrib",
                                 f"Background-Design-Kuliah-Maghrib-01-{kod}.png"),
            },
            "penceramah_master": b.get("penceramah_master",
                                       "data/penceramah-master.json"),
            "ustaz_tile_dir": b.get("ustaz_tile_dir",
                                    "assets/ustaz/kuliah-individu-ustaz"),
            "output_root": b.get("output_root",
                                 f"output/{b.get('tahun', 2026)}/"
                                 f"Jadual Kuliah Individu - {kod}"),
            "output_bulanan": b.get("output_bulanan",
                                    f"output/{b.get('tahun', 2026)}"),
        })
        K.save_json("data/masjid.json", fail)
        return self._json({"ok": True, "kod": kod})

    def _simpan_penceramah(self) -> None:
        b = self._badan_json()
        kanon = (b.get("kanon") or "").strip().upper()
        if not kanon:
            return self._json({"ralat": "kanon diperlukan"}, 400)

        fail = K.load_json("data/penceramah-master.json")
        rekod = fail["penceramah"].get(kanon, {})
        for medan in ("gelaran", "nama_poster", "nama_fail", "tile", "tajuk"):
            if medan in b:
                rekod[medan] = b[medan]
        if "nama_baris" in b:
            baris = b["nama_baris"]
            rekod["nama_baris"] = baris if baris else None
        rekod.setdefault("gelaran", "YBhg Al-Fadhil")
        rekod.setdefault("nama_poster", kanon.title())
        rekod.setdefault("tile", None)
        rekod.setdefault("tajuk", "")
        rekod.setdefault("nama_baris", None)
        fail["penceramah"][kanon] = rekod
        K.save_json("data/penceramah-master.json", fail)
        return self._json({"ok": True, "kanon": kanon, "rekod": rekod})

    # ------------------------------------------------------------------
    # Ubah / tambah / buang satu slot kuliah dalam jadual bulanan.
    #
    # Nama penceramah masuk ke fail jadual bulanan; tajuk yang berbeza
    # daripada tajuk lalai penceramah masuk ke fail tindihan per-tarikh —
    # struktur yang sama seperti yang dibaca render_individu.py.
    # ------------------------------------------------------------------
    def _simpan_jadual(self) -> None:
        b = self._badan_json()
        try:
            tahun, bulan = (int(x) for x in (b.get("bulan") or "").split("-"))
            hari = str(int(b["hari"]))
        except (ValueError, KeyError, TypeError):
            return self._json({"ralat": "bulan (YYYY-MM) dan hari diperlukan"}, 400)

        slot = b.get("slot")
        if slot not in ("subuh", "maghrib"):
            return self._json({"ralat": "slot mesti 'subuh' atau 'maghrib'"}, 400)

        slug = S.bulan_slug(bulan)
        p = K.ROOT / "data" / str(tahun) / f"{slug}.json"
        if not p.exists():
            return self._json({"ralat": f"fail jadual tiada: {slug}.json"}, 404)
        data = json.loads(p.read_text(encoding="utf-8"))

        akhir = int(data.get("hari_dalam_bulan") or 31)
        if not 1 <= int(hari) <= akhir:
            return self._json({"ralat": f"hari mesti antara 1 dan {akhir}"}, 400)

        masjid = (K.cari_masjid(b["masjid"]) if b.get("masjid")
                  else K.senarai_masjid()[0])
        master = K.load_penceramah(masjid)
        kanon = (b.get("kanon") or "").strip().upper()
        if kanon and kanon not in master:
            return self._json(
                {"ralat": f"'{kanon}' tiada dalam registry penceramah"}, 400)

        ov_path = K.ROOT / "data" / str(tahun) / "individu" / f"{slug}.json"
        ov = (json.loads(ov_path.read_text(encoding="utf-8"))
              if ov_path.exists() else {})
        ov.setdefault("jadual", {})

        def buang(h: str, s: str) -> None:
            info = data["jadual"].get(h)
            if info:
                info.pop(s, None)
                if not info:
                    data["jadual"][h] = {"maghrib": ""}
            if h in ov["jadual"]:
                ov["jadual"][h].pop(s, None)
                if not ov["jadual"][h]:
                    del ov["jadual"][h]

        # Slot dipindahkan ke tarikh/slot lain — kosongkan kedudukan asal.
        h0, s0 = b.get("hari_asal"), b.get("slot_asal")
        if h0 and s0 and (str(int(h0)) != hari or s0 != slot):
            buang(str(int(h0)), s0)

        ganti_event = None
        info = data["jadual"].setdefault(hari, {})
        if kanon:
            if info.get("event"):
                ganti_event = info.pop("event")
            info[slot] = kanon
        else:
            buang(hari, slot)

        # Tajuk: simpan tindihan hanya kalau berbeza daripada tajuk lalai.
        tajuk = (b.get("tajuk") or "").strip()
        lalai = (master.get(kanon, {}).get("tajuk") or "") if kanon else ""
        if kanon and tajuk and tajuk != lalai:
            ov["jadual"].setdefault(hari, {})[slot] = {"tajuk": tajuk}
        elif kanon:
            if hari in ov["jadual"]:
                ov["jadual"][hari].pop(slot, None)
                if not ov["jadual"][hari]:
                    del ov["jadual"][hari]

        p.write_text(BB.jadi_teks(data), encoding="utf-8")

        if ov["jadual"]:
            ov_path.parent.mkdir(parents=True, exist_ok=True)
            ov_path.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        elif ov_path.exists():
            ov_path.unlink()

        return self._json({"ok": True, "hari": int(hari), "slot": slot,
                           "kanon": kanon or None, "event_diganti": ganti_event})


def main() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"Papan Kawalan Jadual Kuliah  ->  {url}")
    print(f"Root projek: {K.ROOT}")
    print("Tekan Ctrl+C untuk berhenti.\n")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBerhenti.")


if __name__ == "__main__":
    main()
