# -*- mode: python ; coding: utf-8 -*-
import shutil
from PyInstaller.utils.hooks import collect_all

datas = [('firmware', 'firmware'), ('core', 'core'), ('assets', 'assets')]
_esptool = shutil.which('esptool.exe') or shutil.which('esptool')
binaries = [(_esptool, '.')] if _esptool else []
hiddenimports = ['serial', 'serial.tools', 'serial.tools.list_ports', 'customtkinter', 'esptool', 'qrcode', 'qrcode.image.pil', 'PIL._tkinter_finder', 'core.lang', 'core.detector', 'core.flasher', 'core.provisioner', 'core.config_manager', 'core.qr_generator']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('esptool')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AgroCommish',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
