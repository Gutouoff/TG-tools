# -*- mode: python ; coding: utf-8 -*-
# TG工具箱 Web 版打包配置 (PyInstaller onedir)
# 用法: python -m PyInstaller TG工具箱Web.spec
# 产物: dist/TG工具箱Web/TG工具箱Web.exe (pywebview + FastAPI + Svelte 前端)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
hiddenimports += collect_submodules('telethon')
hiddenimports += collect_submodules('opentele')
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('pywebview')
hiddenimports += collect_submodules('websockets')
hiddenimports += collect_submodules('starlette')

datas = [('界面文本.txt', '.')]
datas += [('webapp/dist', 'webapp/dist')]
datas += collect_data_files('pywebview')

a = Analysis(
    ['web_main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'ttkbootstrap', 'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui',
              'PyQt5.QtWidgets', 'PyQt5.QtNetwork', 'sip'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TG工具箱Web',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TG工具箱Web',
)
