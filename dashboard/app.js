/* Papan Kawalan Jadual Kuliah — vanilla JS, tiada build step. */
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const state = {
  data: null,        // respons /api/state
  kodMasjid: null,
  bulanTerpilih: null, // "2026-08"
  job: null,
};

const kunciBulan = (b) => `${b.tahun}-${String(b.bulan).padStart(2, '0')}`;
const bulanSemasa = () =>
  (state.data?.bulan || []).find((b) => kunciBulan(b) === state.bulanTerpilih);

// --------------------------------------------------------------- utiliti
async function api(laluan, pilihan = {}) {
  let r;
  try {
    r = await fetch(laluan, pilihan);
  } catch {
    // fetch hanya gagal begini bila pelayan tempatan tidak berjalan
    throw new Error('Pelayan dashboard tidak berjalan. Klik dua kali MULA-DASHBOARD.bat, '
                    + 'kemudian cuba lagi — data dalam borang ini tidak hilang.');
  }
  const teks = await r.text();
  let badan;
  try { badan = teks ? JSON.parse(teks) : {}; } catch { badan = { ralat: teks }; }
  if (!r.ok) throw new Error(badan.ralat || `HTTP ${r.status}`);
  return badan;
}

let toastTimer;
function toast(msg, buruk = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.toggle('bad', buruk);
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 4200);
}

const esc = (s) => String(s ?? '').replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function bukaFolder(path) {
  try {
    const r = await api('/api/buka-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    if (!r.ok) toast('Folder belum wujud — ia akan dicipta semasa penjanaan.', true);
  } catch (e) { toast(e.message, true); }
}

// ------------------------------------------------------------ muat state
async function muatState() {
  const q = state.kodMasjid ? `?masjid=${encodeURIComponent(state.kodMasjid)}` : '';
  state.data = await api('/api/state' + q);
  state.kodMasjid = state.data.masjid_aktif.kod;

  const senarai = state.data.bulan;
  if (!state.bulanTerpilih || !senarai.some((b) => kunciBulan(b) === state.bulanTerpilih)) {
    // Default: bulan pertama yang belum selesai, jika tiada -> yang terakhir.
    const belum = senarai.find((b) => b.peringkat === 'belum-mula' || b.peringkat === 'separuh');
    state.bulanTerpilih = kunciBulan(belum || senarai[senarai.length - 1]);
  }
  lukisSemua();
}

function lukisSemua() {
  lukisRail();
  lukisPilihBulan();
  lukisPilihMasjid();
  lukisPipeline();
  lukisTindakan();
  lukisIndividu();
  lukisPenceramah();
  lukisMasjid();
}

// ----------------------------------------------------------------- rail
function lukisRail() {
  const m = state.data.masjid_aktif;
  $('#rail-masjid').textContent = `${m.kod} · ${m.nama}`;
  const n = state.data.penceramah.tanpa_gambar.length;
  const b = $('#badge-penceramah');
  b.hidden = n === 0;
  b.textContent = n;
}

function lukisPilihBulan() {
  const sel = $('#pilih-bulan');
  sel.innerHTML = state.data.bulan.map((b) => {
    const tanda = { 'selesai': '✓', 'separuh': '◐', 'belum-mula': '○', 'tiada-data': '·' }[b.peringkat];
    return `<option value="${kunciBulan(b)}" ${kunciBulan(b) === state.bulanTerpilih ? 'selected' : ''}>
              ${tanda} ${esc(b.label)}</option>`;
  }).join('');
}

function lukisPilihMasjid() {
  $('#pilih-masjid').innerHTML = state.data.senarai_masjid.map((m) => `
    <label class="radio-card ${m.kod === state.kodMasjid ? 'is-on' : ''}">
      <input type="radio" name="masjid" value="${esc(m.kod)}"
             ${m.kod === state.kodMasjid ? 'checked' : ''}>
      <span><strong>${esc(m.nama)}</strong><small>Kod ${esc(m.kod)}</small></span>
    </label>`).join('');
}

// -------------------------------------------------------------- pipeline
function chip(kelas, teks) { return `<span class="chip ${kelas}">${esc(teks)}</span>`; }

function lukisPipeline() {
  const b = bulanSemasa();
  if (!b) return;
  const ind = b.individu;
  const adaSumber = b.sumber.fail.length > 0;

  // Langkah mana yang seterusnya?
  let langkahSeterusnya = 1;
  if (adaSumber && b.ada_data) langkahSeterusnya = 2;
  if (b.bulanan.siap) langkahSeterusnya = 3;

  const kad = [];

  // --- Langkah 1: sumber ---
  kad.push(`
    <div class="step ${langkahSeterusnya === 1 ? 'is-next' : ''}" data-no="1">
      <h3>Sumber dari AJK</h3>
      ${adaSumber ? chip('ok', `${b.sumber.fail.length} fail diterima`)
                  : chip('', 'Belum ada muat naik')}
      <p>Muat naik imej kalendar untuk <strong>${esc(b.label)}</strong>.</p>
      <div class="dropzone" id="dropzone">
        Seret imej ke sini, atau klik untuk pilih fail
        <input type="file" id="input-fail" accept="image/*,.pdf" hidden multiple>
      </div>
      ${adaSumber ? `<ul class="file-list">${b.sumber.fail.slice(0, 5)
          .map((f) => `<li>${esc(f)}</li>`).join('')}</ul>` : ''}
      <div class="act">
        ${adaSumber && !b.ada_data
          ? `<button class="btn btn-sm btn-utama" data-mentah>Isi &amp; jana JSON →</button>` : ''}
        <button class="btn btn-ghost btn-sm" data-buka="${esc(b.sumber.folder)}">Buka folder input</button>
      </div>
    </div>`);

  // --- Langkah 2: jadual bulanan ---
  const dataChip = b.ada_data
    ? chip('ok', 'Data jadual sedia')
    : chip('stop', 'Data jadual tiada');
  kad.push(`
    <div class="step ${langkahSeterusnya === 2 ? 'is-next' : ''}" data-no="2">
      <h3>Jadual Kuliah Bulanan</h3>
      ${b.bulanan.siap ? chip('ok', `Siap · ${esc(b.label)}`) : dataChip}
      <p>${b.ada_data
            ? `Menjana satu poster kalendar penuh untuk ${esc(b.label)}.`
            : `Isi jadual daripada imej AJK untuk menghasilkan
               <code>data/${b.tahun}/${esc(b.slug)}.json</code>.`}</p>
      <div class="act">
        ${b.ada_data
          ? `<button class="btn btn-sm" data-jana="bulanan">
               ${b.bulanan.siap ? 'Jana semula' : 'Jana jadual bulanan'}</button>
             <button class="btn btn-ghost btn-sm" data-mentah>Ubah data</button>`
          : `<button class="btn btn-sm" data-mentah>Isi data jadual</button>`}
        <button class="btn btn-ghost btn-sm" data-buka="${esc(b.bulanan.folder)}">Buka folder</button>
      </div>
    </div>`);

  // --- Langkah 3: kuliah individu ---
  let indChip;
  if (ind.jumlah_dijangka === 0)         indChip = chip('', 'Tiada slot');
  else if (ind.jumlah_siap === 0)        indChip = chip('', `0 / ${ind.jumlah_dijangka} poster`);
  else if (ind.jumlah_siap < ind.jumlah_dijangka)
    indChip = chip('warn', `${ind.jumlah_siap} / ${ind.jumlah_dijangka} poster`);
  else                                   indChip = chip('ok', `Selesai · ${ind.jumlah_dijangka} poster`);

  kad.push(`
    <div class="step ${langkahSeterusnya === 3 ? 'is-next' : ''}" data-no="3">
      <h3>Kuliah Individu</h3>
      ${indChip}
      ${ind.jumlah_tertangguh
          ? `<p>${ind.jumlah_tertangguh} poster tertangguh — gambar penceramah belum ada.</p>`
          : `<p>Satu poster untuk setiap slot Subuh &amp; Maghrib.</p>`}
      <div class="act">
        <button class="btn btn-sm" data-jana="individu"
                ${ind.jumlah_boleh_jana ? '' : 'disabled'}>
          Jana ${ind.jumlah_boleh_jana || 0} poster
        </button>
        <button class="btn btn-ghost btn-sm" data-buka="${esc(ind.folder)}">Buka folder</button>
      </div>
    </div>`);

  $('#pipeline').innerHTML = kad.join('');
  pasangDropzone();
}

// ------------------------------------------------------------- tindakan
function lukisTindakan() {
  const b = bulanSemasa();
  const kad = $('#kad-tindakan');
  if (!b) { kad.hidden = true; return; }

  const bhg = [];

  if (b.tak_dikenali.length) {
    bhg.push(`<p class="hint" style="margin-bottom:6px">
      <strong>Nama tidak dikenali dalam registry</strong> — tambah dalam tab Penceramah:</p>
      <ul class="file-list">${b.tak_dikenali
        .map((t) => `<li>${esc(t.tarikh)} · ${esc(t.slot)} · ${esc(t.nama)}</li>`).join('')}</ul>`);
  }

  if (b.individu.tertangguh.length) {
    bhg.push(`<p class="hint" style="margin:12px 0 6px">
      <strong>Gambar berbingkai belum disediakan</strong> — potong gambar dan simpan dalam
      <code>${esc(state.data.penceramah.tile_dir)}</code>, kemudian kemas kini lajur
      <em>Gambar</em> dalam tab Penceramah:</p>
      <ul class="file-list">${b.individu.tertangguh
        .map((t) => `<li>${esc(t.tarikh)} · ${esc(t.nama_poster)}</li>`).join('')}</ul>
      <div class="act" style="margin-top:10px">
        <button class="btn btn-ghost btn-sm"
                data-buka="${esc(state.data.penceramah.tile_dir)}">Buka folder gambar</button>
      </div>`);
  }

  kad.hidden = bhg.length === 0;
  $('#senarai-tindakan').innerHTML = bhg.join('');
}

// ------------------------------------------------------------- individu
function lukisIndividu() {
  const b = bulanSemasa();
  if (!b) return;
  const ind = b.individu;

  $('#individu-tajuk').textContent = `Kuliah Individu — ${b.label}`;
  $('#individu-folder').textContent = ind.folder;
  $('#individu-bar').style.width =
    ind.jumlah_dijangka ? `${(ind.jumlah_siap / ind.jumlah_dijangka) * 100}%` : '0%';
  $('#btn-jana-individu').disabled = !ind.jumlah_boleh_jana;
  $('#btn-jana-individu').textContent =
    ind.jumlah_boleh_jana ? `Jana ${ind.jumlah_boleh_jana} poster` : 'Tiada yang boleh dijana';

  $('#tbl-individu tbody').innerHTML = ind.senarai.length
    ? ind.senarai.map((r) => `
      <tr>
        <td class="num">${esc(r.tarikh)}</td>
        <td>${r.slot === 'subuh' ? 'Subuh' : 'Maghrib'}</td>
        <td>${esc(r.nama_poster)}</td>
        <td class="muted">${esc(r.tajuk || '—')}</td>
        <td>${r.ada_gambar ? chip('ok', 'Ada') : chip('stop', 'Tiada')}</td>
        <td>${r.siap
              ? `<a href="/fail?path=${encodeURIComponent(ind.folder + '/' + r.fail)}"
                    target="_blank">${chip('ok', 'Lihat')}</a>`
              : chip('', 'Belum')}</td>
        <td style="text-align:right">
          <button class="btn btn-ghost btn-sm"
                  data-slot-ubah="${esc(r.tarikh)}|${esc(r.slot)}">Ubah</button>
        </td>
      </tr>`).join('')
    : `<tr><td colspan="7" class="muted">Tiada slot kuliah untuk bulan ini.</td></tr>`;
}

// ------------------------------------------------------------ penceramah
let cachePenceramah = null;
async function lukisPenceramah() {
  if (!cachePenceramah) cachePenceramah = await api('/api/penceramah');
  const tapis = $('#cari-penceramah').value.trim().toLowerCase();
  const rekod = Object.entries(cachePenceramah.penceramah)
    .filter(([k, v]) => !tapis
      || k.toLowerCase().includes(tapis)
      || (v.nama_poster || '').toLowerCase().includes(tapis));

  $('#tbl-penceramah tbody').innerHTML = rekod.map(([kanon, v]) => `
    <tr>
      <td><code>${esc(kanon)}</code></td>
      <td>${esc(v.nama_poster)}</td>
      <td class="muted">${esc(v.tajuk || '—')}</td>
      <td>${v.tile
        ? `<span class="tile-sel">
             <img class="tile-mini" alt="" loading="lazy" src="${esc(urlTile(v.tile))}">
             <span class="muted tile-nama">${esc(v.tile)}</span>
           </span>`
        : chip('stop', 'Belum ada')}</td>
      <td style="text-align:right">
        <button class="btn btn-ghost btn-sm" data-gambar="${esc(kanon)}">Gambar</button>
        <button class="btn btn-ghost btn-sm" data-edit="${esc(kanon)}">Ubah</button>
      </td>
    </tr>`).join('');
}

// --------------------------------------------------------------- masjid
function lukisMasjid() {
  $('#tbl-masjid tbody').innerHTML = state.data.senarai_masjid.map((m) => `
    <tr>
      <td><code>${esc(m.kod)}</code></td>
      <td>${esc(m.nama)}</td>
      <td class="muted">${esc(m.nama_poster)}</td>
      <td class="muted">${esc(m.output_root)}</td>
      <td>${m.aktif ? chip('ok', 'Aktif') : chip('', 'Tidak aktif')}</td>
    </tr>`).join('');
}

// ------------------------------------------------------------------ job
async function janaKerja(jenis) {
  const b = bulanSemasa();
  if (!b) return;
  $('#kad-log').hidden = false;
  $('#log-teks').textContent = '';
  $('#log-status').className = 'chip run';
  $('#log-status').textContent = 'Berjalan…';
  $$('[data-jana]').forEach((el) => { el.disabled = true; });

  try {
    const { job } = await api('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jenis, masjid: state.kodMasjid,
                             tahun: b.tahun, bulan: b.bulan }),
    });
    state.job = job;
    tinjauJob(job);
  } catch (e) {
    toast(e.message, true);
    $('#log-status').className = 'chip stop';
    $('#log-status').textContent = 'Gagal';
    $$('[data-jana]').forEach((el) => { el.disabled = false; });
  }
}

async function tinjauJob(job) {
  const j = await api(`/api/job/${job}`);
  $('#log-teks').textContent = j.log.join('\n');
  $('#log-teks').scrollTop = $('#log-teks').scrollHeight;

  if (j.status === 'berjalan' || j.status === 'menunggu') {
    setTimeout(() => tinjauJob(job), 700);
    return;
  }
  const ok = j.status === 'selesai';
  $('#log-status').className = `chip ${ok ? 'ok' : 'stop'}`;
  $('#log-status').textContent = ok ? 'Selesai' : 'Gagal';
  toast(ok ? 'Penjanaan selesai.' : 'Penjanaan gagal — semak log.', !ok);
  cachePenceramah = null;
  await muatState();
}

// -------------------------------------------------------------- dropzone
function pasangDropzone() {
  const zon = $('#dropzone');
  if (!zon) return;
  const input = $('#input-fail');

  zon.onclick = () => input.click();
  input.onchange = () => hantarFail([...input.files]);

  ['dragenter', 'dragover'].forEach((ev) => zon.addEventListener(ev, (e) => {
    e.preventDefault(); zon.classList.add('is-over');
  }));
  ['dragleave', 'drop'].forEach((ev) => zon.addEventListener(ev, (e) => {
    e.preventDefault(); zon.classList.remove('is-over');
  }));
  zon.addEventListener('drop', (e) => hantarFail([...e.dataTransfer.files]));
}

async function hantarFail(fail) {
  const b = bulanSemasa();
  if (!b || !fail.length) return;
  for (const f of fail) {
    const fd = new FormData();
    fd.append('tahun', b.tahun);
    fd.append('bulan', b.bulan);
    fd.append('fail', f, f.name);
    try {
      await api('/api/upload', { method: 'POST', body: fd });
    } catch (e) { toast(`${f.name}: ${e.message}`, true); return; }
  }
  toast(`${fail.length} fail dimuat naik ke folder input.`);
  await muatState();
}

// ------------------------------------------------------------------ init
function tukarView(nama) {
  $$('.nav-item').forEach((n) => n.classList.toggle('is-active', n.dataset.view === nama));
  $$('.view').forEach((v) => { v.hidden = v.id !== `view-${nama}`; });
  const tajuk = {
    aliran:     ['Aliran Kerja', 'Ikut langkah 1 → 3 untuk bulan yang dipilih.'],
    individu:   ['Kuliah Individu', 'Satu poster untuk setiap slot Subuh dan Maghrib.'],
    penceramah: ['Penceramah', 'Registry nama, gelaran dan kitab untuk poster individu.'],
    tetapan:    ['Masjid & Surau', 'Daftar lokasi baharu dan lihat tetapan sedia ada.'],
  }[nama];
  $('#tajuk-view').textContent = tajuk[0];
  $('#sub-view').textContent = tajuk[1];
}

document.addEventListener('click', (e) => {
  // Nota: pautan 'Penjanaan Manual' juga .nav-item tetapi tiada data-view —
  // biarkan pelayar melayari seperti biasa.
  const nav = e.target.closest('.nav-item[data-view]');
  if (nav) return tukarView(nav.dataset.view);

  const buka = e.target.closest('[data-buka]');
  if (buka) return bukaFolder(buka.dataset.buka);

  const jana = e.target.closest('[data-jana]');
  if (jana) return janaKerja(jana.dataset.jana);

  if (e.target.closest('[data-mentah]')) return bukaMentah();

  const slotUbah = e.target.closest('[data-slot-ubah]');
  if (slotUbah) {
    const [tarikh, slot] = slotUbah.dataset.slotUbah.split('|');
    return bukaBorangSlot(tarikh, slot);
  }

  const gambar = e.target.closest('[data-gambar]');
  if (gambar) return bukaPilihGambar(gambar.dataset.gambar);

  const edit = e.target.closest('[data-edit]');
  if (edit) return ubahPenceramah(edit.dataset.edit);
});

document.addEventListener('change', async (e) => {
  if (e.target.name === 'masjid') {
    state.kodMasjid = e.target.value;
    state.bulanTerpilih = null;
    cachePenceramah = null;
    await muatState();
  }
});

$('#pilih-bulan').addEventListener('change', (e) => {
  state.bulanTerpilih = e.target.value;
  lukisSemua();
});
$('#btn-segar').addEventListener('click', () => { cachePenceramah = null; muatState(); });
$('#cari-penceramah').addEventListener('input', lukisPenceramah);
$('#btn-jana-individu').addEventListener('click', () => janaKerja('individu'));
$('#btn-buka-individu').addEventListener('click', () => bukaFolder(bulanSemasa().individu.folder));
$('#btn-buka-tile').addEventListener('click', () => bukaFolder(state.data.penceramah.tile_dir));

async function ubahPenceramah(kanon) {
  const v = cachePenceramah.penceramah[kanon];
  const nama = prompt(`Nama pada poster untuk ${kanon}:`, v.nama_poster);
  if (nama === null) return;
  const tajuk = prompt('Tajuk / kitab lalai:', v.tajuk || '');
  if (tajuk === null) return;
  await simpanPenceramah({ kanon, nama_poster: nama, tajuk, nama_baris: null });
}

async function simpanPenceramah(medan) {
  try {
    await api('/api/penceramah', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(medan),
    });
    toast('Registry dikemas kini.');
    cachePenceramah = null;
    await muatState();
  } catch (e) { toast(e.message, true); }
}

// ------------------------------------------------------- pemilih gambar
// Gambar dipilih daripada fail yang MEMANG ada dalam folder — tiada lagi
// menaip nama fail, jadi tiada lagi silap ejaan atau fail yang tak wujud.
let cacheGambar = null;
let gambarUntuk = null;

function urlTile(nama) {
  const dir = (cacheGambar && cacheGambar.dir) || 'assets/ustaz/kuliah-individu-ustaz';
  return `/fail?path=${encodeURIComponent(dir + '/' + nama)}`;
}

async function bukaPilihGambar(kanon) {
  gambarUntuk = kanon;
  const v = cachePenceramah.penceramah[kanon];
  const q = state.kodMasjid ? `?masjid=${encodeURIComponent(state.kodMasjid)}` : '';
  try {
    cacheGambar = await api('/api/gambar' + q);
  } catch (e) { return toast(e.message, true); }

  $('#pilih-tajuk').textContent = v.nama_poster || kanon;
  $('#pilih-sub').textContent =
    `${cacheGambar.fail.length} fail dalam ${cacheGambar.dir}`;
  $('#pilih-cari').value = '';
  lukisPilihGambar();
  $('#lapis-gambar').hidden = false;
  $('#pilih-cari').focus();
}

function lukisPilihGambar() {
  const tapis = $('#pilih-cari').value.trim().toLowerCase();
  const kini = cachePenceramah.penceramah[gambarUntuk].tile;
  const senarai = cacheGambar.fail.filter((f) => !tapis
    || f.nama.toLowerCase().includes(tapis));

  $('#pilih-grid').innerHTML = senarai.length
    ? senarai.map((f) => {
      const kelas = ['tile-kad'];
      if (f.nama === kini) kelas.push('terpilih');
      if (f.guna && f.guna !== gambarUntuk) kelas.push('dipakai');
      const nota = f.nama === kini ? 'Gambar semasa'
        : (f.guna && f.guna !== gambarUntuk ? `Dipakai: ${f.guna}` : 'Belum dipakai');
      return `<button type="button" class="${kelas.join(' ')}" data-fail="${esc(f.nama)}">
                <img alt="" loading="lazy" src="${esc(urlTile(f.nama))}">
                <b>${esc(f.nama)}</b>
                <small>${esc(nota)}</small>
              </button>`;
    }).join('')
    : '<p class="muted">Tiada fail yang sepadan.</p>';
}

function tutupPilihGambar() {
  $('#lapis-gambar').hidden = true;
  gambarUntuk = null;
}

$('#pilih-cari').addEventListener('input', lukisPilihGambar);
$('#pilih-batal').addEventListener('click', tutupPilihGambar);
$('#lapis-gambar').addEventListener('click', (e) => {
  if (e.target.id === 'lapis-gambar') tutupPilihGambar();
});
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  if (!$('#lapis-daftar').hidden) return tutupDaftar();   // popup teratas dahulu
  if (!$('#lapis-gambar').hidden) tutupPilihGambar();
  if (!$('#lapis-slot').hidden) tutupBorangSlot();
  if (!$('#lapis-mentah').hidden) tutupMentah();
});
$('#pilih-kosong').addEventListener('click', async () => {
  const kanon = gambarUntuk;
  tutupPilihGambar();
  await simpanPenceramah({ kanon, tile: null });
});
// --------------------------------------------------- ubah / tambah slot
// Nama penceramah disimpan dalam fail jadual bulanan; tajuk yang berbeza
// daripada tajuk lalai penceramah disimpan sebagai tindihan per-tarikh.
let slotAsal = null;   // { hari, slot } bila mengubah; null bila menambah

async function bukaBorangSlot(tarikh, slot) {
  const b = bulanSemasa();
  if (!b) return;
  if (!cachePenceramah) cachePenceramah = await api('/api/penceramah');

  const rekod = tarikh
    ? b.individu.senarai.find((r) => r.tarikh === tarikh && r.slot === slot)
    : null;
  slotAsal = rekod ? { hari: Number(tarikh.slice(-2)), slot } : null;

  const senarai = Object.entries(cachePenceramah.penceramah)
    .sort((a, x) => a[0].localeCompare(x[0]));
  $('#slot-kanon').innerHTML = '<option value="">— kosongkan slot —</option>'
    + senarai.map(([k, v]) =>
      `<option value="${esc(k)}"${rekod && rekod.kanon === k ? ' selected' : ''}>
         ${esc(v.nama_poster || k)}</option>`).join('');

  $('#slot-tajuk').textContent = rekod ? 'Ubah slot kuliah' : 'Tambah slot kuliah';
  $('#slot-sub').textContent = `${b.label} — disimpan ke data/${b.tahun}/${b.slug}.json`;
  $('#slot-hari').value = rekod ? Number(tarikh.slice(-2)) : '';
  $('#slot-hari').max = b.hari_dalam_bulan || 31;
  $('#slot-slot').value = rekod ? slot : 'maghrib';
  $('#slot-tajuk-teks').value = rekod && rekod.tajuk_ditindih ? rekod.tajuk : '';
  $('#slot-buang').hidden = !rekod;
  kemasHintTajuk();

  $('#lapis-slot').hidden = false;
  $('#slot-hari').focus();
}

function kemasHintTajuk() {
  const k = $('#slot-kanon').value;
  const v = k && cachePenceramah.penceramah[k];
  $('#slot-tajuk-hint').textContent = v && v.tajuk
    ? `Kosongkan untuk guna tajuk lalai: ${v.tajuk}`
    : 'Penceramah ini tiada tajuk lalai.';
}

function tutupBorangSlot() {
  $('#lapis-slot').hidden = true;
  slotAsal = null;
}

async function simpanSlot(kosongkan = false) {
  const b = bulanSemasa();
  const hari = Number($('#slot-hari').value);
  if (!hari) return toast('Isikan tarikh dahulu.', true);

  const badan = {
    bulan: `${b.tahun}-${String(b.bulan).padStart(2, '0')}`,
    masjid: state.kodMasjid,
    hari,
    slot: $('#slot-slot').value,
    kanon: kosongkan ? '' : $('#slot-kanon').value,
    tajuk: kosongkan ? '' : $('#slot-tajuk-teks').value,
  };
  if (slotAsal) { badan.hari_asal = slotAsal.hari; badan.slot_asal = slotAsal.slot; }

  try {
    const r = await api('/api/jadual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(badan),
    });
    tutupBorangSlot();
    toast(r.event_diganti
      ? `Jadual dikemas kini. Acara "${r.event_diganti.split('\n')[0]}" pada hari itu telah diganti.`
      : 'Jadual dikemas kini.');
    await muatState();
  } catch (e) { toast(e.message, true); }
}

$('#btn-tambah-slot').addEventListener('click', () => bukaBorangSlot(null, null));
$('#slot-kanon').addEventListener('change', kemasHintTajuk);
$('#slot-batal').addEventListener('click', tutupBorangSlot);
$('#slot-simpan').addEventListener('click', () => simpanSlot(false));
$('#slot-buang').addEventListener('click', () => simpanSlot(true));
$('#borang-slot').addEventListener('submit', (e) => { e.preventDefault(); simpanSlot(false); });
$('#lapis-slot').addEventListener('click', (e) => {
  if (e.target.id === 'lapis-slot') tutupBorangSlot();
});

$('#pilih-grid').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-fail]');
  if (!btn) return;
  const kanon = gambarUntuk;
  const tile = btn.dataset.fail;
  tutupPilihGambar();
  await simpanPenceramah({ kanon, tile });
});

$('#borang-masjid').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(e.target));
  try {
    await api('/api/masjid', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fd),
    });
    toast(`${fd.kod} didaftarkan.`);
    e.target.reset();
    await muatState();
  } catch (err) { toast(err.message, true); }
});

// ------------------------------------------- isi jadual daripada imej AJK
// Borang harian -> /api/mentah -> buat_bulan.py -> data/<tahun>/<MM>-<bulan>.json.
// Setiap nama disemak (tanpa menulis) semasa menaip supaya salah ejaan
// dan nama baharu kelihatan SEBELUM fail dijana.
const mentah = { borang: null, hari: [], mus: [], hasil: null, berubah: false,
                 imej: 0, timer: null, seq: 0, asalEjaan: {} };

const JENIS = { kuliah: 'Kuliah', yasin: 'Yasin & Tahlil', acara: 'Acara lain' };

async function bukaMentah() {
  const b = bulanSemasa();
  if (!b) return;
  let f;
  try {
    f = await api(`/api/mentah?bulan=${kunciBulan(b)}`);
  } catch (e) { return toast(e.message, true); }

  Object.assign(mentah, {
    borang: f, hasil: null, berubah: false, imej: 0, asalEjaan: {},
    hari: f.hari.map((r) => ({ ...r })),
    mus: f.muslimat.map((m) => ({ ...m })),
  });

  $('#dl-penceramah').innerHTML = f.penceramah.map((n) => `<option value="${esc(n)}">`).join('');
  $('#dl-ustazah').innerHTML = f.ustazah.map((n) => `<option value="${esc(n)}">`).join('');
  $('#mentah-tajuk').textContent = `Isi jadual — ${f.label}`;
  $('#mentah-asal').textContent = {
    data: `Dimuat daripada ${f.fail_data}`,
    mentah: 'Dimuat daripada jadual-mentah.txt',
    baharu: 'Borang baharu',
  }[f.asal];
  $('#mentah-jana').textContent = f.ada_data ? 'Jana semula fail JSON' : 'Jana fail JSON';

  lukisImejMentah();
  lukisHariMentah();
  lukisMusMentah();
  lukisRingkasMentah();
  $('#lapis-mentah').hidden = false;
  semakMentah();
}

function tutupMentah(paksa = false) {
  if (!paksa && mentah.berubah
      && !confirm('Perubahan dalam borang belum dijana. Tutup dan buang perubahan?')) return;
  $('#lapis-mentah').hidden = true;
  clearTimeout(mentah.timer);
}

// ---- imej sumber
function lukisImejMentah() {
  const sumber = mentah.borang.sumber;
  const ada = sumber.length > 0;
  $('#mentah-tab').innerHTML = sumber.length > 1
    ? sumber.map((s, i) => `<button type="button" data-imej="${i}"
         class="${i === mentah.imej ? 'is-on' : ''}" title="${esc(s)}">
         ${i + 1}. ${esc(s.split('/').pop())}</button>`).join('')
    : '';
  const img = $('#mentah-img');
  img.hidden = !ada;
  $('#mentah-tiada-imej').hidden = ada;
  $('#mentah-penuh').hidden = !ada;
  $('#mentah-kanvas').classList.remove('zum');
  if (ada) {
    const url = `/fail?path=${encodeURIComponent(sumber[mentah.imej])}`;
    img.src = url;
    $('#mentah-penuh').href = url;
  }
}

$('#mentah-tab').addEventListener('click', (e) => {
  const t = e.target.closest('[data-imej]');
  if (!t) return;
  mentah.imej = Number(t.dataset.imej);
  lukisImejMentah();
});
$('#mentah-kanvas').addEventListener('click', () => {
  if (mentah.borang?.sumber.length) $('#mentah-kanvas').classList.toggle('zum');
});

// ---- baris harian
function selMentah(r) {
  if (r.jenis === 'yasin') {
    return '<td colspan="2" class="ev">Bacaan Yasin &amp; Tahlil · Imam Bertugas</td>';
  }
  if (r.jenis === 'acara') {
    return `<td colspan="2"><input data-f="acara" value="${esc(r.acara)}"
              placeholder="cth: Majlis Sambutan Maulidur Rasul"></td>`;
  }
  const ahad = r.nama_hari === 'Ahad';
  const medan = (slot) => `<td>
      <input data-f="${slot}" list="dl-penceramah" value="${esc(r[slot])}"
             placeholder="${slot === 'subuh' && !ahad ? '—' : 'Nama penceramah'}">
      <span class="padan" data-p="${r.hari}|${slot}"></span></td>`;
  return medan('subuh') + medan('maghrib');
}

function barisMentah(r) {
  return `<tr data-h="${r.hari}" class="${r.nama_hari === 'Ahad' ? 'ahad' : ''}">
    <td class="tkh">${r.hari}<small>${esc(r.nama_hari)}</small></td>
    <td><select data-f="jenis">${Object.entries(JENIS).map(([k, v]) =>
      `<option value="${k}" ${r.jenis === k ? 'selected' : ''}>${v}</option>`).join('')}
    </select></td>
    ${selMentah(r)}
  </tr>`;
}

function lukisHariMentah() {
  $('#mentah-hari').innerHTML = mentah.hari.map(barisMentah).join('');
}

$('#mentah-hari').addEventListener('input', (e) => {
  const tr = e.target.closest('tr[data-h]');
  const f = e.target.dataset.f;
  if (!tr || !f) return;
  const r = mentah.hari.find((x) => x.hari === Number(tr.dataset.h));
  r[f] = e.target.value;
  delete mentah.asalEjaan[`${r.hari}|${f}`];   // pengguna menaip semula
  if (f === 'jenis') {
    tr.outerHTML = barisMentah(r);
    const baru = $(`#mentah-hari tr[data-h="${r.hari}"] input`);
    if (baru) baru.focus();
  }
  ubahMentah();
});

// ---- kuliah muslimat
function lukisMusMentah() {
  $('#mentah-mus').innerHTML = mentah.mus.length
    ? mentah.mus.map((m, i) => `<tr data-i="${i}">
        <td><input data-f="hari" type="number" min="1" max="${mentah.hari.length}"
                   value="${esc(m.hari)}" placeholder="Hari"></td>
        <td><input data-f="jam" value="${esc(m.jam)}" placeholder="9:00 PAGI"></td>
        <td><input data-f="nama" list="dl-ustazah" value="${esc(m.nama)}" placeholder="Nama ustazah">
            <span class="padan" data-p="${esc(m.hari)}|muslimah"></span></td>
        <td><button type="button" class="btn-x" data-buang="${i}" title="Buang baris">×</button></td>
      </tr>`).join('')
    : '<tr><td colspan="4" class="muted">Tiada kuliah muslimat. Klik “Tambah baris” jika ada.</td></tr>';
}

$('#mentah-mus').addEventListener('input', (e) => {
  const tr = e.target.closest('tr[data-i]');
  const f = e.target.dataset.f;
  if (!tr || !f) return;
  const m = mentah.mus[Number(tr.dataset.i)];
  delete mentah.asalEjaan[`${m.hari}|muslimah`];
  m[f] = f === 'hari' ? (e.target.value ? Number(e.target.value) : '') : e.target.value;
  if (f === 'hari') $('.padan', tr).dataset.p = `${m.hari}|muslimah`;
  ubahMentah();
});
$('#mentah-mus').addEventListener('click', (e) => {
  const x = e.target.closest('[data-buang]');
  if (!x) return;
  mentah.mus.splice(Number(x.dataset.buang), 1);
  lukisMusMentah();
  ubahMentah();
});
$('#mentah-tambah-mus').addEventListener('click', () => {
  mentah.mus.push({ hari: '', jam: '', nama: '' });
  lukisMusMentah();
  $('#mentah-mus tr:last-child input').focus();
});

// ---- semakan langsung
function ubahMentah() {
  mentah.berubah = true;
  clearTimeout(mentah.timer);
  mentah.timer = setTimeout(semakMentah, 450);
}

function badanMentah(lebih = {}) {
  return JSON.stringify({
    bulan: `${mentah.borang.tahun}-${String(mentah.borang.bulan).padStart(2, '0')}`,
    hari: mentah.hari,
    muslimat: mentah.mus,
    ...lebih,
  });
}

async function semakMentah() {
  const seq = ++mentah.seq;
  try {
    const h = await api('/api/mentah', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: badanMentah(),
    });
    if (seq !== mentah.seq) return;   // ada semakan lebih baharu
    mentah.hasil = h;
    lukisPadanMentah();
    lukisRingkasMentah();
  } catch (e) {
    if (seq !== mentah.seq) return;
    mentah.hasil = null;
    $('#mentah-ringkas').innerHTML = chip('stop', e.message);
  }
}

// Tetapkan nilai satu medan nama (DOM + model) — dipakai oleh auto-isi,
// butang "Guna nama ini" dan selepas daftar penceramah baharu.
function setNamaMentah(input, nilai) {
  input.value = nilai;
  const tr = input.closest('tr');
  const f = input.dataset.f;
  if (tr.dataset.h) {
    mentah.hari.find((x) => x.hari === Number(tr.dataset.h))[f] = nilai;
  } else if (tr.dataset.i !== undefined) {
    mentah.mus[Number(tr.dataset.i)][f] = nilai;
  }
  mentah.berubah = true;
}

function lukisPadanMentah() {
  const { padanan, hilang } = mentah.hasil;
  let ditukar = false;
  $$('#lapis-mentah .padan').forEach((el) => {
    const input = el.previousElementSibling;
    const nilai = input ? input.value.trim() : '';
    const p = padanan[el.dataset.p];
    const muslimah = el.dataset.p.endsWith('|muslimah');
    el.className = 'padan';
    el.innerHTML = '';
    if (!nilai || !p) return;

    // Padanan yakin -> terus guna nama standard. Medan yang sedang ditaip
    // dibiarkan dahulu; ia ditukar sebaik sahaja pengguna keluar dari medan.
    if ((p.tahap === 'tepat' || p.tahap === 'auto') && p.nama && nilai !== p.nama) {
      if (document.activeElement !== input) {
        mentah.asalEjaan[el.dataset.p] = nilai;
        setNamaMentah(input, p.nama);
        ditukar = true;
      }
    }
    const asal = mentah.asalEjaan[el.dataset.p];

    if (p.tahap === 'tepat' || p.tahap === 'auto') {
      el.classList.add('ok');
      el.textContent = (asal && asal !== input.value
        ? `✓ Diseragamkan daripada “${asal}”` : '✓ Dalam rekod')
        + (p.sumber ? ` · ikut ${p.sumber}` : '');
    } else if (p.tahap === 'sahkan') {
      el.classList.add('warn');
      el.innerHTML = `? Mungkin <b>${esc(p.nama)}</b>
        <button type="button" class="btn-pautan" data-guna="${esc(p.nama)}">Guna nama ini</button>
        ${muslimah ? '' : '<button type="button" class="btn-pautan" data-daftar>+ Daftar baharu</button>'}`;
    } else {
      el.classList.add('stop');
      el.innerHTML = muslimah
        ? '✗ Tiada dalam rekod ustazah (ustazah-master.json)'
        : `✗ Tiada dalam rekod
           <button type="button" class="btn-pautan" data-daftar>+ Daftar penceramah baharu</button>`;
    }
    const kanon = p.tahap === 'tiada' ? null : (asal ? input.value : p.nama);
    if (kanon && hilang.includes(kanon)) {
      el.insertAdjacentHTML('beforeend', ' · <span class="warn">tiada gambar jadual bulanan</span>');
    }
  });
  // Nama telah ditukar kepada ejaan standard -> kira semula ringkasan isu.
  if (ditukar) {
    clearTimeout(mentah.timer);
    mentah.timer = setTimeout(semakMentah, 50);
  }
}

// Butang dalam petunjuk padanan
$('#lapis-mentah').addEventListener('click', (e) => {
  const guna = e.target.closest('[data-guna]');
  const daftar = e.target.closest('[data-daftar]');
  if (!guna && !daftar) return;
  const input = e.target.closest('td').querySelector('input');
  if (guna) {
    setNamaMentah(input, guna.dataset.guna);
    clearTimeout(mentah.timer);
    semakMentah();
  } else {
    bukaDaftar(input);
  }
});

// Keluar dari medan nama -> semak serta-merta supaya auto-isi berlaku.
$('#lapis-mentah').addEventListener('change', (e) => {
  if (!e.target.matches('input[list]')) return;
  clearTimeout(mentah.timer);
  semakMentah();
});

// ------------------------------------------------ daftar penceramah baharu
const daftar = { input: null, mentah: '', sentuh: {} };

// "UST DR.ALIHANAFIAH" -> "USTAZ DR. ALIHANAFIAH" (ikut gaya rekod sedia ada)
function namaStandard(mentahNama) {
  const t = mentahNama.toUpperCase().replace(/\./g, '. ').replace(/[^A-Z0-9'. -]/g, ' ')
    .split(/\s+/).map((x) => x.replace(/\.+$/, '')).filter(Boolean);
  const bersih = t.filter((x) => !['UST', 'USTZ', 'USTAZ'].includes(x))
    .map((x) => (x === 'DR' ? 'DR.' : x));
  return (bersih[0] === 'IMAM' ? bersih : ['USTAZ', ...bersih]).join(' ');
}

function namaPoster(kanon) {
  const kecil = { BIN: 'bin', BINTI: 'binti' };
  const titik = { HJ: 'Hj.', LT: 'Lt.', KOL: 'Kol.', 'DR.': 'Dr.' };
  const w = kanon.split(/\s+/).filter(Boolean).map((x) => kecil[x] || titik[x]
    || x.charAt(0) + x.slice(1).toLowerCase());
  return (w[0] === 'Imam' ? ['Ustaz', ...w] : w).join(' ');
}

function failGambar(kanon) {
  const w = kanon.replace(/\./g, '').split(/\s+/).filter((x) => x && x !== 'USTAZ')
    .map((x) => x.charAt(0) + x.slice(1).toLowerCase());
  return `Ustaz-${w.join('-')}.png`;
}

function kemasDaftar() {
  const kanon = $('#daftar-kanon').value.trim().toUpperCase();
  if (!daftar.sentuh.poster) $('#daftar-poster').value = namaPoster(kanon);
  if (!daftar.sentuh.gambar) $('#daftar-gambar').value = failGambar(kanon);
  const g = $('#daftar-gambar').value.trim();
  const ada = mentah.borang.gambar_bulanan.some((f) => f.toLowerCase() === g.toLowerCase());
  $('#daftar-gambar-hint').textContent = ada
    ? '✓ Fail gambar ini sudah ada.'
    : 'Fail belum ada — simpan gambar dengan nama ini dalam assets/ustaz/. '
      + 'Sementara itu jadual bulanan guna gambar placeholder.';
  $('#daftar-ralat').textContent = '';
}

async function bukaDaftar(input) {
  daftar.input = input;
  daftar.mentah = input.value.trim();
  daftar.sentuh = {};
  $('#daftar-mentah').textContent = daftar.mentah;
  $('#daftar-kanon').value = namaStandard(daftar.mentah);
  $('#daftar-tajuk-kitab').value = '';
  $('#daftar-gelaran').value = 'YBhg Al-Fadhil';
  $('#dl-gambar-bulanan').innerHTML = mentah.borang.gambar_bulanan
    .map((f) => `<option value="${esc(f)}">`).join('');

  const q = state.kodMasjid ? `?masjid=${encodeURIComponent(state.kodMasjid)}` : '';
  try {
    const g = await api('/api/gambar' + q);
    $('#daftar-tile').innerHTML = '<option value="">Belum ada — poster individu ditangguh</option>'
      + g.fail.map((f) => `<option value="${esc(f.nama)}">${esc(f.nama)}${
        f.guna ? ` (dipakai: ${esc(f.guna)})` : ''}</option>`).join('');
  } catch { $('#daftar-tile').innerHTML = '<option value="">Belum ada</option>'; }

  kemasDaftar();
  $('#lapis-daftar').hidden = false;
  $('#daftar-kanon').focus();
  $('#daftar-kanon').select();
}

function tutupDaftar() {
  $('#lapis-daftar').hidden = true;
  daftar.input = null;
}

async function simpanDaftar() {
  const kanon = $('#daftar-kanon').value.trim().toUpperCase();
  if (!kanon) return ($('#daftar-ralat').textContent = 'Isikan nama standard.');
  try {
    const r = await api('/api/penceramah-baru', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kanon,
        nama_poster: $('#daftar-poster').value.trim(),
        gelaran: $('#daftar-gelaran').value.trim(),
        tajuk: $('#daftar-tajuk-kitab').value.trim(),
        gambar_bulanan: $('#daftar-gambar').value.trim(),
        tile: $('#daftar-tile').value,
      }),
    });

    // Masukkan ke dropdown & isi setiap medan yang ditaip dengan ejaan yang sama.
    mentah.borang.penceramah = [...mentah.borang.penceramah, r.kanon].sort();
    $('#dl-penceramah').innerHTML = mentah.borang.penceramah
      .map((n) => `<option value="${esc(n)}">`).join('');
    const sasaran = daftar.mentah.toUpperCase();
    $$('#mentah-hari input[list="dl-penceramah"]').forEach((el) => {
      if (el === daftar.input || el.value.trim().toUpperCase() === sasaran) {
        setNamaMentah(el, r.kanon);
      }
    });
    cachePenceramah = null;
    tutupDaftar();
    toast(`${r.kanon} didaftarkan${r.gambar_ada ? '' : ' — gambar jadual bulanan belum ada'}.`);
    clearTimeout(mentah.timer);
    semakMentah();
  } catch (e) {
    $('#daftar-ralat').textContent = e.message;
  }
}

$('#daftar-kanon').addEventListener('input', kemasDaftar);
$('#daftar-poster').addEventListener('input', () => { daftar.sentuh.poster = true; });
$('#daftar-gambar').addEventListener('input', () => { daftar.sentuh.gambar = true; kemasDaftar(); });
$('#daftar-simpan').addEventListener('click', simpanDaftar);
$('#borang-daftar').addEventListener('submit', (e) => { e.preventDefault(); simpanDaftar(); });
$('#daftar-batal').addEventListener('click', tutupDaftar);
$('#lapis-daftar').addEventListener('click', (e) => {
  if (e.target.id === 'lapis-daftar') tutupDaftar();
});

function lukisRingkasMentah() {
  const h = mentah.hasil;
  if (!h) { $('#mentah-ringkas').innerHTML = chip('run', 'Menyemak…'); return; }
  const i = h.isu;
  const c = [];
  if (i.tiada)  c.push(chip('stop', `${i.tiada} nama tiada dalam registry`));
  if (i.sahkan) c.push(chip('warn', `${i.sahkan} perlu disahkan`));
  if (i.hilang) c.push(chip('warn', `${i.hilang} tiada gambar jadual bulanan`));
  if (i.kosong) c.push(chip('', `${i.kosong} hari belum diisi`));
  if (i.separa) c.push(chip('', `${i.separa} hari Ahad separa`));
  if (i.auto)   c.push(chip('ok', `${i.auto} ejaan diseragamkan`));
  if (!i.tiada && !i.sahkan && !i.hilang && !i.kosong && !i.separa) c.unshift(chip('ok', 'Sedia dijana'));
  $('#mentah-ringkas').innerHTML = c.join('');
}

async function janaMentah() {
  clearTimeout(mentah.timer);
  await semakMentah();
  const f = mentah.borang;
  const i = mentah.hasil?.isu;
  if (!i) return toast('Semakan gagal — betulkan ralat dahulu.', true);

  const belum = i.tiada + i.sahkan + i.hilang + i.kosong;
  if (belum && !confirm(`Masih ada ${belum} perkara belum lengkap (lihat bahagian bawah borang).\n`
                        + 'Jana fail JSON juga? Anda boleh ubah semula kemudian.')) return;
  if (f.ada_data && !confirm(`${f.fail_data} sudah wujud dan akan diganti.\n`
                             + 'Salinan lama disimpan sebagai .json.bak. Teruskan?')) return;

  const btn = $('#mentah-jana');
  btn.disabled = true;
  try {
    const h = await api('/api/mentah', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: badanMentah({ tulis: true, ganti: f.ada_data }),
    });
    toast(`${h.fail_data} berjaya dijana.`);
    tutupMentah(true);
    await muatState();
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
  }
}

$('#mentah-jana').addEventListener('click', janaMentah);
$('#mentah-batal').addEventListener('click', () => tutupMentah());
$('#lapis-mentah').addEventListener('click', (e) => {
  if (e.target.id === 'lapis-mentah') tutupMentah();
});

muatState().catch((e) => toast(e.message, true));
