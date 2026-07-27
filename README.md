# Jadual Kuliah Masjid As-Salam — Auto Render

Repo ni simpan semua aset jadual kuliah dan render PNG + PDF **automatik**
dalam GitHub sendiri (guna GitHub Actions). Tak perlu Photoshop, tak perlu
render manual di komputer.

---

## Susunan folder

```
assets/                aset tetap (jarang tukar)
  khat-header.png      design tulisan khat
  logo-masjid.png      logo masjid
  qr-infaq.png         QR code infaq
  ustaz/               gambar ustaz dah crop siap
    amin-qusyairi.jpg
    adam-azhari.jpg
    ...

data/
  ustaz-master.json    senarai ejaan STANDARD + nama fail gambar
  2026/
    08-ogos.json       ← EDIT SINI je tiap bulan
    09-september.json

template/jadual.html   design (setup sekali)
scripts/render.py      enjin render
output/2026/           PNG + PDF keluar SINI automatik
```

---

## Setup kali pertama (sekali sahaja)

1. Buat repo **private** baru di GitHub, upload semua fail ni.
2. Masukkan gambar ustaz dalam `assets/ustaz/` — nama fail kena
   **sama** dengan yang tercatat dalam `data/ustaz-master.json`.
3. Masukkan `khat-header.png`, `logo-masjid.png`, `qr-infaq.png` dalam `assets/`.
   (Kalau belum ada, render tetap jalan — guna teks/placeholder sementara.)

---

## Kerja tiap bulan

1. **Salin** fail bulan lepas, contoh `data/2026/08-ogos.json`
   → jadikan `data/2026/09-september.json`.
2. **Edit** dalam fail baru tu:
   - `bulan`, `tahun`
   - `mula_hari` — hari pertama bulan jatuh hari apa
     (Isnin=0, Selasa=1, Rabu=2, Khamis=3, Jumaat=4, Sabtu=5, Ahad=6)
   - `hari_dalam_bulan` — 28/29/30/31
   - `jadual` — nama ustaz ikut tarikh
   - `muslimah` — jadual kuliah muslimah
3. **Push** ke GitHub.
4. Pergi tab **Actions** → pilih **Render Jadual Kuliah** → klik
   **Run workflow** → taip path fail (cth `data/2026/09-september.json`)
   → **Run**.
5. Tunggu ~1 minit. PNG + PDF akan muncul dalam `output/2026/`
   (auto-commit), dan juga boleh download dari halaman Actions
   (bahagian "Artifacts").

---

## Semakan nama automatik

Kalau nama ustaz dalam fail data **tak sama** dengan ejaan standard
dalam `ustaz-master.json`, render akan **gagal** (Actions jadi merah)
dan tunjuk nama mana yang salah. Ni elak silap ejaan lepas senyap.

Betulkan salah satu:
- **Betulkan ejaan** dalam fail data supaya sama dengan master, ATAU
- **Tambah nama baru** dalam `ustaz-master.json` (kalau ustaz baru).

Nama ustaz baru: tambah baris dalam `ustaz-master.json`:
```json
"USTAZ NAMA BARU": "nama-baru.jpg"
```
dan letak gambar `nama-baru.jpg` dalam `assets/ustaz/`.

---

## Uji di komputer sendiri (optional)

```bash
pip install playwright
python -m playwright install chromium
python scripts/render.py data/2026/08-ogos.json
```
