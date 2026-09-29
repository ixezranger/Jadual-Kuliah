# Panduan Mula — Langkah demi Langkah

Cara buka dan guna Papan Kawalan Jadual Kuliah.

---

## Penting dahulu

Fail HTML dalam folder `dashboard/` **tidak boleh** dibuka dengan klik dua kali.

Sebabnya: halaman itu perlu membaca fail jadual anda dan menjalankan enjin
render — kedua-duanya berlaku di komputer anda, bukan dalam pelayar. Jadi
ia mesti dihidangkan oleh pelayan tempatan.

Kalau anda klik dua kali `index.html`, halaman akan terbuka tetapi kosong.

**Cara betul: mulakan pelayan dahulu, pelayar akan buka sendiri.**

---

## Persediaan (sekali sahaja)

Hanya **satu** perkara perlu dipasang sendiri: Python.

### Langkah 1 — Pasang Python

Muat turun dari <https://www.python.org/downloads/> dan pasang.
Semasa pemasangan, **tandakan kotak "Add Python to PATH"**.

Untuk menyemak sama ada ia sudah ada, buka **Command Prompt** dan taip:

```bash
python --version
```

Keluar `Python 3.12.x` atau lebih baru — sudah sedia.

> Kalau keluar ralat `'python' is not recognized` tetapi anda yakin Python
> sudah dipasang, jangan risau — `MULA-DASHBOARD.bat` mencari Python sendiri
> di lokasi pemasangan biasa, jadi ia tetap boleh berjalan.

### Langkah 2 — Pakej render

**Tidak perlu buat apa-apa.** Kali pertama `MULA-DASHBOARD.bat` dijalankan,
ia memasang sendiri `playwright` + `pillow` dan memuat turun pelayar render
(lebih kurang 150 MB). Cukup sekali sahaja; kali seterusnya terus jalan.

Kalau mahu pasang manual:

```bash
python -m pip install playwright pillow
```

```bash
python -m playwright install chromium
```

---

## Guna setiap bulan

### Langkah 1 — Hidupkan sistem

Klik dua kali fail **`MULA-DASHBOARD.bat`** dalam folder projek.

> **Klik dua kali sahaja — jangan guna "Run as administrator".**
> Tetingkap admin tidak memuatkan PATH pengguna, jadi Python selalunya
> tidak dijumpai di situ.

Satu tetingkap hitam akan terbuka dan memaparkan:

```
  [OK] Python dijumpai: Python 3.12.10

  Memulakan pelayan... pelayar akan buka sendiri.
```

Papan kawalan berada di <http://127.0.0.1:8765/>.

Pelayar akan terbuka sendiri.

> **Biarkan tetingkap hitam itu terbuka** selagi anda guna dashboard.
> Kalau ditutup, dashboard akan berhenti berfungsi.

*Kalau lebih suka guna Command Prompt:*

```bash
cd "D:\KHALIFAH TERRITORY 2026\01. WEBSITE PROJECT 2026\Jadual Kuliah Masjid As-Salam"
```

```bash
python scripts\serve_dashboard.py
```

### Langkah 2 — Pilih Masjid / Surau

Pada kad **1 · Pilih Masjid / Surau**, klik butang radio.
Buat masa ini ada satu sahaja: *M0001 — Masjid As-Salam, Petaling Permai*.

### Langkah 3 — Pilih bulan kerja

Di bar atas sebelah kanan ada pemilih **Bulan kerja**.
Sistem sudah auto-pilih bulan pertama yang belum siap. Tanda di sebelah nama:

| Tanda | Maksud |
|-------|--------|
| `✓` | Semua poster sudah siap |
| `◐` | Siap sebahagian |
| `○` | Belum mula |
| `·` | Tiada data jadual lagi |

### Langkah 4 — Muat naik imej kalendar dari AJK

Pada kad **1 · Sumber dari AJK**, seret imej ke kotak bertitik,
atau klik kotak itu untuk pilih fail.

Fail disimpan ke `input/<tahun>/<bulan>/`.

### Langkah 5 — Sediakan fail jadual bulan itu

Sistem tidak membaca imej secara automatik — anda taip jadual ke dalam
fail JSON, seperti biasa:

```
data/2026/09-september.json
```

Salin format dari `data/2026/08-ogos.json` yang sedia ada.

### Langkah 6 — Semak "Perlu tindakan anda"

Selepas fail jadual disimpan, klik butang **⟳** di bar atas.

Kalau ada penceramah baharu atau penceramah tanpa gambar, satu panel
kuning akan muncul di bawah dengan senarai nama dan tarikh.

Untuk setiap nama dalam senarai:

1. Sediakan gambar berbingkai — **938 × 1458 px PNG, latar telus**,
   sudah termasuk bingkai gerbang (bukan potongan kosong).
2. Simpan dalam `assets/ustaz/kuliah-individu-ustaz/`
   dengan nama `ki-Nama-Penceramah.png`.
3. Pergi ke tab **Penceramah**, cari nama itu, klik **Ubah**,
   masukkan nama fail tersebut.

Klik **Buka folder gambar** untuk terus ke folder yang betul.

### Langkah 7 — Jana Jadual Bulanan

Pada kad **2 · Jadual Kuliah Bulanan**, klik **Jana jadual bulanan**.

Log akan muncul di bawah. Tunggu sehingga status bertukar **Selesai**.

### Langkah 8 — Jana Kuliah Individu

Pada kad **3 · Kuliah Individu**, klik **Jana N poster**.

Ambil masa lebih kurang **3 saat setiap poster** (satu bulan penuh ≈ 1 minit).

Selesai nanti, kad akan tunjuk `29 / 29 poster`.

### Langkah 9 — Buka folder hasil

Klik **Buka folder** pada kad Kuliah Individu.
File Explorer akan terus buka:

```
output/2026/Jadual Kuliah Individu/09-September-2026/
```

---

## Poster satu-satu (penjanaan manual)

Untuk jemputan khas, ganti penceramah, atau pindaan tajuk:

1. Klik **Penjanaan Manual** di menu kiri.
2. Pilih slot (Subuh / Maghrib), penceramah, dan tarikh.
   Tarikh Masihi dan Hijri diisi automatik.
3. Ubah mana-mana teks — pratonton di sebelah kanan berubah serta-merta.
4. Klik **Jana & simpan JPG**.

Poster masuk ke folder bulan yang sama seperti penjanaan pukal.

---

## Bila sudah selesai

Tutup tetingkap hitam, atau tekan **Ctrl+C** di dalamnya.

---

## Masalah biasa

| Masalah | Penyelesaian |
|---------|--------------|
| Halaman kosong / "This site can't be reached" | Tetingkap hitam sudah tertutup. Klik dua kali `MULA-DASHBOARD.bat` semula. |
| `[X] Python tidak dijumpai` | Python belum dipasang. Pasang dari python.org dan **tandakan "Add Python to PATH"**. |
| `'python' is not recognized` bila taip sendiri di Command Prompt | Python ada tetapi tiada dalam PATH. Guna `MULA-DASHBOARD.bat` (ia cari sendiri), atau pasang semula Python dengan "Add Python to PATH" ditanda. |
| Buka sebagai *Administrator* lalu kata Python tiada | Tutup tetingkap itu. Klik dua kali `MULA-DASHBOARD.bat` biasa — tidak perlu hak admin. |
| Butang "Jana" kelabu tidak boleh klik | Semua yang boleh dijana sudah siap, atau semua penceramah tersisa tiada gambar. Semak panel *Perlu tindakan anda*. |
| Log kata `Executable doesn't exist` | Jalankan `python -m playwright install chromium`. |
| Port 8765 sudah diguna | Tutup tetingkap hitam yang lama, atau tetapkan port lain: `set KI_PORT=8766` sebelum jalankan. |
| Poster lama tidak berubah walaupun jana semula | Sistem melangkau fail sedia ada. Guna CLI: `python scripts\render_individu.py --bulan 2026-09 --force` |

---

## Rujukan lanjut

Butiran teknikal (struktur data, reka bentuk poster, rujukan CLI) ada dalam
[KULIAH-INDIVIDU.md](KULIAH-INDIVIDU.md).
