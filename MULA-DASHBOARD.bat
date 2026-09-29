@echo off
setlocal enabledelayedexpansion
REM ===================================================================
REM  Papan Kawalan Jadual Kuliah — pelancar satu-klik
REM  Klik dua kali fail ini. Pelayar akan buka sendiri.
REM  Biarkan tetingkap hitam ini terbuka semasa guna dashboard.
REM  NOTA: Tak perlu "Run as administrator".
REM ===================================================================
title Papan Kawalan Jadual Kuliah
cd /d "%~dp0"

echo.
echo   Papan Kawalan Jadual Kuliah
echo   ---------------------------
echo.

REM --- Cari Python (tidak bergantung pada PATH sahaja) ---
set "PY="

REM  1) Python Launcher (py.exe)
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY=py -3"

REM  2) python dalam PATH
if not defined PY (
  python -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)

REM  3) Lokasi pemasangan biasa
if not defined PY (
  for %%D in (
    "%LOCALAPPDATA%\Programs\Python"
    "%ProgramFiles%"
    "%ProgramFiles(x86)%"
    "C:\"
  ) do (
    if not defined PY (
      for /d %%P in ("%%~D\Python3*") do (
        if not defined PY if exist "%%~fP\python.exe" set "PY="%%~fP\python.exe""
      )
    )
  )
)

REM  4) Profil pengguna lain (jika tetingkap ini dibuka sebagai admin lain)
if not defined PY (
  for /d %%U in ("C:\Users\*") do (
    for /d %%P in ("%%~fU\AppData\Local\Programs\Python\Python3*") do (
      if not defined PY if exist "%%~fP\python.exe" set "PY="%%~fP\python.exe""
    )
  )
)

if not defined PY (
  echo   [X] Python tidak dijumpai.
  echo.
  echo       Pasang Python dari https://www.python.org/downloads/
  echo       Semasa pemasangan, TANDAKAN "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

for /f "delims=" %%V in ('%PY% --version 2^>^&1') do set "PYVER=%%V"
echo   [OK] Python dijumpai: !PYVER!
echo.

REM --- Semak pakej yang diperlukan ---
%PY% -c "import playwright, PIL" >nul 2>&1
if errorlevel 1 (
  echo   [!] Pakej belum lengkap. Memasang sekarang...
  echo.
  %PY% -m pip install --quiet playwright pillow
  echo.
)

REM --- Pastikan pelayar Chromium (untuk render poster) ada ---
REM  Tanpa ini render gagal dengan "Executable doesn't exist" (cth. selepas
REM  tukar laptop atau selepas Playwright dikemas kini). Jika sudah ada,
REM  arahan ini selesai dalam beberapa saat tanpa memuat turun apa-apa.
echo   Menyemak pelayar Chromium untuk render poster...
%PY% -m playwright install chromium
if errorlevel 1 (
  echo   [!] Gagal memasang Chromium. Semak sambungan internet dan cuba lagi.
) else (
  echo   [OK] Chromium sedia.
)
echo.

echo   Memulakan pelayan... pelayar akan buka sendiri.
echo   Tekan Ctrl+C atau tutup tetingkap ini untuk berhenti.
echo.

%PY% scripts\serve_dashboard.py

echo.
echo   Pelayan berhenti.
pause
