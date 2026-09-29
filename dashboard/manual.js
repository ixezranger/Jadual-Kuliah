/* Alat penjanaan manual — komposisi satu poster Kuliah Individu. */
'use strict';

const $ = (s, r = document) => r.querySelector(s);

let MASJID = [];
let PENCERAMAH = {};
let nyahlantun;

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
  toastTimer = setTimeout(() => { t.hidden = true; }, 4500);
}

const slotTerpilih = () => document.querySelector('[name=slot]:checked').value;
const masjidTerpilih = () => MASJID.find((m) => m.kod === $('#f-masjid').value);

// -------------------------------------------------------------- muat awal
async function mula() {
  const state = await api('/api/state');
  MASJID = state.senarai_masjid;
  $('#f-masjid').innerHTML = MASJID
    .map((m) => `<option value="${m.kod}">${m.kod} · ${m.nama}</option>`).join('');

  PENCERAMAH = (await api('/api/penceramah')).penceramah;
  $('#f-penceramah').innerHTML =
    '<option value="">— isi sendiri —</option>' +
    Object.entries(PENCERAMAH)
      .map(([k, v]) => `<option value="${k}"${v.tile ? '' : ' data-notile="1"'}>
            ${v.nama_poster}${v.tile ? '' : '  (tiada gambar)'}</option>`).join('');

  const hariIni = new Date();
  $('#f-tarikh').value = hariIni.toISOString().slice(0, 10);
  $('#f-lokasi').value = MASJID[0].nama_poster;
  $('#f-hadis').value =
    'Barangsiapa yang menempuh suatu jalan untuk mencari ilmu,\n' +
    'maka Allah memudahkan untuknya jalan menuju ke Syurga.';
  $('#f-riwayat').value = '(Hadis Riwayat Muslim)';

  await isiTarikh();
  pasangPeristiwa();
  skalaPratonton();
  jadualPratonton();
}

function pasangPeristiwa() {
  $('#f-penceramah').addEventListener('change', () => {
    const v = PENCERAMAH[$('#f-penceramah').value];
    if (!v) return;
    $('#f-nama').value = (v.nama_baris && v.nama_baris.length)
      ? v.nama_baris.join('\n')
      : `${v.gelaran || ''} ${v.nama_poster}`.trim();
    $('#f-tajuk').value = v.tajuk || '';
    kemasNamaFail();
    jadualPratonton();
  });

  $('#f-tarikh').addEventListener('change', async () => {
    await isiTarikh();
    jadualPratonton();
  });

  $('#f-masjid').addEventListener('change', () => {
    $('#f-lokasi').value = masjidTerpilih().nama_poster;
    jadualPratonton();
  });

  document.querySelectorAll('[name=slot]').forEach((el) =>
    el.addEventListener('change', () => { kemasNamaFail(); jadualPratonton(); }));

  ['f-masihi', 'f-hijri', 'f-nama', 'f-tajuk', 'f-lokasi', 'f-hadis', 'f-riwayat']
    .forEach((id) => $('#' + id).addEventListener('input', jadualPratonton));

  $('#btn-segar').addEventListener('click', () => muatPratonton());
  $('#btn-simpan').addEventListener('click', simpan);
  window.addEventListener('resize', skalaPratonton);
}

async function isiTarikh() {
  const t = $('#f-tarikh').value;
  if (!t) return;
  const d = await api(`/api/tarikh?tarikh=${t}`);
  $('#f-masihi').value = d.masihi;
  $('#f-hijri').value = d.hijri;
  kemasNamaFail();
}

function kemasNamaFail() {
  const kanon = $('#f-penceramah').value;
  const v = PENCERAMAH[kanon];
  const nama = v ? (v.nama_fail || v.nama_poster)
                 : ($('#f-nama').value.split('\n').pop() || 'Penceramah');
  const t = $('#f-tarikh').value.replaceAll('-', '.');
  const suffix = slotTerpilih() === 'subuh' ? ' (Kuliah Subuh)' : '';
  $('#f-fail').value = `${t} - ${nama}${suffix}.jpg`;
}

// -------------------------------------------------------------- pratonton
function muatanSemasa() {
  return {
    masjid: $('#f-masjid').value,
    slot: slotTerpilih(),
    kanon: $('#f-penceramah').value || null,
    nama_baris: $('#f-nama').value.split('\n').map((s) => s.trim()).filter(Boolean),
    tarikh_masihi: $('#f-masihi').value,
    tarikh_hijri: $('#f-hijri').value,
    tajuk: $('#f-tajuk').value,
    lokasi: $('#f-lokasi').value,
    hadis: $('#f-hadis').value,
    hadis_riwayat: $('#f-riwayat').value,
    fail: $('#f-fail').value,
  };
}

function jadualPratonton() {
  clearTimeout(nyahlantun);
  $('#chip-pratonton').className = 'chip run';
  $('#chip-pratonton').textContent = 'Mengemas kini…';
  nyahlantun = setTimeout(muatPratonton, 450);
}

async function muatPratonton() {
  const m = muatanSemasa();
  if (!m.kanon) {
    $('#chip-pratonton').className = 'chip warn';
    $('#chip-pratonton').textContent = 'Pilih penceramah (untuk gambar)';
    return;
  }
  try {
    const r = await fetch('/api/template', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(m),
    });
    if (!r.ok) throw new Error((await r.json()).ralat || 'gagal');
    $('#pratonton').srcdoc = await r.text();
    $('#chip-pratonton').className = 'chip ok';
    $('#chip-pratonton').textContent = 'Terkini';
  } catch (e) {
    $('#chip-pratonton').className = 'chip stop';
    $('#chip-pratonton').textContent = e.message;
  }
}

function skalaPratonton() {
  const kotak = $('#stage-box');
  $('#pratonton').style.transform = `scale(${kotak.clientWidth / 3000})`;
}

// ----------------------------------------------------------------- simpan
async function simpan() {
  const btn = $('#btn-simpan');
  btn.disabled = true;
  $('#status').textContent = 'Menjana…';
  try {
    const r = await api('/api/render-manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...muatanSemasa(), tarikh: $('#f-tarikh').value }),
    });
    $('#status').innerHTML =
      `Disimpan: <code>${r.path}</code> — <a href="/fail?path=${encodeURIComponent(r.path)}"
       target="_blank">buka imej</a>`;
    toast('Poster dijana.');
  } catch (e) {
    $('#status').textContent = '';
    toast(e.message, true);
  } finally {
    btn.disabled = false;
  }
}

mula().catch((e) => toast(e.message, true));
