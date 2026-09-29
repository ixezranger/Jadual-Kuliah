# Sistem Poster Kuliah Individu

Menjana poster **Kuliah Subuh** dan **Kuliah Maghrib** (3000 × 1689 px JPG),
satu poster untuk setiap slot dalam jadual bulanan.

---

## Mula cepat

```bash
python scripts/serve_dashboard.py
```

Papan kawalan terbuka di <http://127.0.0.1:8765/>.

Untuk penjanaan tanpa UI:

```bash
python scripts/render_individu.py --bulan 2026-08
```

---

## Aliran kerja

| # | Langkah | Di mana |
|---|---------|---------|
| 1 | Terima imej kalendar dari AJK | — |
| 2 | Pilih Masjid/Surau | Papan Kawalan → butang radio |
| 3 | Muat naik imej ke folder input | Papan Kawalan → seret & lepas |
| 4 | Sistem semak penceramah baharu | automatik — dipapar di *Perlu tindakan anda* |
| 5 | Pilih bulan (auto-kesan bulan seterusnya) | pemilih *Bulan kerja* di bar atas |
| 6 | Jana Jadual Bulanan | Papan Kawalan → langkah 2 |
| 7 | Jana Kuliah Individu | Papan Kawalan → langkah 3 |
| 8 | Buka folder output | butang *Buka folder* pada setiap kad |

Bar status setiap langkah menunjukkan bulan terakhir yang siap dan berapa
poster masih tertangguh.

---

## Fail data (tiada pangkalan data)

| Fail | Peranan |
|------|---------|
| `data/masjid.json` | Senarai Masjid/Surau. Kod `M0001` = Masjid As-Salam, Petaling Permai. |
| `data/penceramah-master.json` | Registry penceramah: gelaran, nama poster, pecahan baris, kitab, fail gambar. |
| `data/<tahun>/<MM>-<bulan>.json` | Jadual bulanan (input kepada kedua-dua penjana). |
| `data/<tahun>/individu/<MM>-<bulan>.json` | *Pilihan* — tindih tajuk untuk tarikh tertentu. |
| `input/<tahun>/<MM>-<bulan>/` | Imej kalendar asal dari AJK. |
| `output/<tahun>/Jadual Kuliah Individu/<MM>-<Bulan>-<tahun>/` | Poster siap. |

### Menindih tajuk untuk satu tarikh

Seorang penceramah boleh mengajar kitab berbeza pada tarikh berbeza
(contoh: Ustaz Hj. Hisyam Zakaria — *Bahrul Mazi* pada 12 Julai,
*As-Safinah An-Najah* pada 24 Julai). Cipta:

```json
// data/2026/individu/08-ogos.json
{
  "jadual": {
    "28": { "maghrib": { "tajuk": "Kitab As-Safinah An-Najah" } }
  }
}
```

---

## Menambah penceramah baharu

1. Potong gambar berbingkai (938 × 1458 px PNG, latar telus) dan simpan dalam
   `assets/ustaz/kuliah-individu-ustaz/` sebagai `ki-<Nama-Dengan-Sengkang>.png`.
   Gambar ini sudah termasuk bingkai gerbang — bukan potongan kosong.
2. Dalam Papan Kawalan → tab **Penceramah** → **Ubah**, isikan nama fail
   tersebut pada medan gambar.

Poster untuk penceramah tanpa gambar akan **dilangkau** (bukan gagal), dan
disenaraikan dalam *Perlu tindakan anda*.

---

## Menambah Masjid/Surau baharu

1. Papan Kawalan → **Masjid & Surau** → borang *Daftar lokasi baharu*.
2. Letak dua fail latar 3000 × 1689 px dalam
   `assets/base-design/kuliah-individu/`:
   - `Background-Design-Kuliah-Subuh-01-<KOD>.png`
   - `Background-Design-Kuliah-Maghrib-01-<KOD>.png`

Setiap lokasi ada folder output sendiri, jadi tiada pertindihan nama fail.

---

## Reka bentuk poster

Semua kedudukan ditakrif sebagai CSS custom property dalam
`template/kuliah-individu.html` (`:root`). Ruang koordinat = 3000 × 1689.

| Elemen | Font | Saiz |
|--------|------|------|
| Dipimpin oleh | Poppins SemiBold Italic | 37.7 px |
| Nama penceramah | Poppins SemiBold | 67 px (auto-kecil kalau panjang) |
| Tarikh Masihi | Poppins SemiBold | 41.3 px |
| Tarikh Hijri | Poppins Regular | 36 px |
| Tajuk / kitab | Poppins SemiBold | 42 px |
| Lokasi | Poppins SemiBold Italic | 41.2 px |
| Hadis | Poppins Medium Italic | 33.2 px |
| Riwayat | Poppins Light | 28.6 px |

Aset tetap: latar mengikut slot, `ki-base-label.png` (satu sprite mengandungi
tab *Dipimpin oleh*, kotak nama, pil tarikh dan pil lokasi) pada (1249, 806),
serta ikon `logo-kalendar.png` dan `logo-bulan.png`.

### Pecahan baris

- **Nama** — diambil dari `nama_baris` dalam registry (disalin daripada poster
  07-Julai-2026, yang disusun secara manual dan tidak konsisten). Kalau
  `nama_baris` kosong, sistem imbangkan lebar dua baris secara automatik.
- **Tajuk** — satu baris kalau ≤ 450 px, jika tidak dipecah dua baris seimbang.
  Pecahan hanya pada ruang, jadi `Al-Maram` tidak terputus pada sempang.

### Kalendar Hijri

`scripts/ki_common.py` guna algoritma jadual (Kuwaiti). Disahkan tepat
terhadap poster 07-Julai-2026: 1 Julai 2026 = 15 Muharram 1448H,
17 Julai = 1 Safar, 31 Julai = 15 Safar.

---

## Penjanaan manual

<http://127.0.0.1:8765/dashboard/manual.html>

Untuk poster sekali-sekala (jemputan, ganti penceramah, pindaan tajuk).
Semua medan boleh diubah, dengan pratonton WYSIWYG langsung.

Alat ini memanggil **enjin render yang sama** dengan penjanaan pukal —
tiada dua enjin yang boleh terpesong hasilnya.

---

## Rujukan CLI

```bash
# satu bulan penuh
python scripts/render_individu.py --bulan 2026-08

# satu poster
python scripts/render_individu.py --tarikh 2026-08-02 --slot maghrib \
       --penceramah "USTAZ ANAS MALEK"

# lihat apa yang akan dijana, tanpa render
python scripts/render_individu.py --bulan 2026-08 --dry-run

# tulis ganti fail sedia ada
python scripts/render_individu.py --bulan 2026-08 --force

# tulis ke folder lain
python scripts/render_individu.py --bulan 2026-08 --out-dir _ujian
```

Tanpa `--force`, fail yang sudah wujud akan dilangkau — selamat untuk
dijalankan berulang kali.

---

## Isu diketahui dalam arkib sedia ada

- `output/2026/Jadual Kuliah Individu/07-Julai-2026/2026.07.17 - Ustaz Jalil Hanafee.jpg`
  sebenarnya memaparkan **Ustaz Najmul Khairi** — nama fail tidak sepadan
  dengan kandungan poster.
- `data/2026/07-julai.json` tiada dalam repo, jadi Julai 2026 dipapar sebagai
  *tiada data* walaupun 32 poster sudah wujud dalam folder output.
