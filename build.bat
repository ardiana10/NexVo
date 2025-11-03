@echo off
title 🚀 Build NexVo Desktop (OneFile EXE)
echo ===============================================
echo    NEXVO DESKTOP BUILD AUTOMATION SCRIPT
echo ===============================================
echo.

REM 🧠 Aktifkan environment virtual
call buildenv\Scripts\activate

REM 🧹 Bersihkan build lama
echo Membersihkan build dan dist lama...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del NexVo.spec 2>nul
echo Selesai membersihkan.
echo.

REM ⚙️ Jalankan PyInstaller (OneFile mode)
echo Memulai proses build NexVo (OneFile, GUI-only)...
pyinstaller --noconfirm --clean ^
    --onefile ^
    --noconsole ^
    --name "NexVo" ^
    --icon "iconKPU.ico" ^
    --version-file "version.txt" ^
    --add-data "Fonts;Fonts" ^
    --add-data "KPU.png;." ^
    --add-data "note.png;." ^
    --add-data "db_manager.py;." ^
    --add-data "init_db.py;." ^
    NexVo.py

IF %ERRORLEVEL% NEQ 0 (
    echo ❌ Build gagal! Periksa error di atas.
    pause
    exit /b
)

echo ✅ Build selesai sukses!
echo.

REM 📦 Salin hasil ke folder PORTABLE
echo Membuat folder Portable...
mkdir Portable 2>nul
copy /Y "dist\NexVo.exe" "Portable\NexVo.exe" >nul

echo.
echo ===============================================
echo ✅ BUILD BERHASIL!
echo 📦 Hasil: Portable\NexVo.exe
echo ===============================================
pause
