@echo off
echo ============================================================
echo   AgroCommish — Generando .EXE con PyInstaller
echo ============================================================

REM Instalar/actualizar dependencias
pip install customtkinter pyserial esptool pyinstaller Pillow "qrcode[pil]" --quiet

REM Buscar esptool en el PATH
for /f "tokens=*" %%i in ('where esptool.exe 2^>nul') do (
    if not defined ESPTOOL set ESPTOOL=%%i
)
if not defined ESPTOOL (
    echo [ERROR] esptool.exe no encontrado. Instala con: pip install esptool
    exit /b 1
)

REM Limpiar builds anteriores
rmdir /s /q build 2>nul
rmdir /s /q dist  2>nul

REM Construir .exe standalone
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "AgroCommish" ^
  --icon=assets\icon.ico ^
  --add-data "firmware;firmware" ^
  --add-data "core;core" ^
  --add-data "assets;assets" ^
  --add-binary "%ESPTOOL%;." ^
  --hidden-import "serial" ^
  --hidden-import "serial.tools" ^
  --hidden-import "serial.tools.list_ports" ^
  --hidden-import "customtkinter" ^
  --hidden-import "esptool" ^
  --hidden-import "qrcode" ^
  --hidden-import "qrcode.image.pil" ^
  --hidden-import "PIL._tkinter_finder" ^
  --hidden-import "core.lang" ^
  --hidden-import "core.detector" ^
  --hidden-import "core.flasher" ^
  --hidden-import "core.provisioner" ^
  --hidden-import "core.config_manager" ^
  --hidden-import "core.qr_generator" ^
  --collect-all "customtkinter" ^
  --collect-all "esptool" ^
  app.py

echo.
if exist "dist\AgroCommish.exe" (
    echo  [OK] EXE listo en:  dist\AgroCommish.exe
    echo.
    echo  Para distribuir copia:
    echo    dist\AgroCommish.exe
    echo    firmware\firmware.bin  ^(junto al .exe en la misma carpeta^)
) else (
    echo  [ERROR] La compilacion fallo. Revisa los mensajes anteriores.
)
echo ============================================================
pause
