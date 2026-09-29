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
  const r = await fetch(laluan, pilihan);
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
            : `Sediakan <code>data/${b.tahun}/${esc(b.slug)}.json</code> dahulu.`}</p>
      <div class="act">
        <button class="btn btn-sm" data-jana="bulanan" ${b.ada_data ? '' : 'disabled'}>
          ${b.bulanan.siap ? 'Jana semula' : 'Jana jadual bulanan'}
        </button>
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
  if (!$('#lapis-gambar').hidden) tutupPilihGambar();
  if (!$('#lapis-slot').hidden) tutupBorangSlot();
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

muatState().catch((e) => toast(e.message, true));
