# -*- mode: python ; coding: utf-8 -*-
# TG工具箱 GUI 打包配置 (PyInstaller onedir 文件夹版)
# 用法: python -m PyInstaller TG工具箱GUI.spec
# 产物: dist/TG工具箱GUI/TG工具箱GUI.exe (含 _internal 依赖,启动快)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
hiddenimports += collect_submodules('telethon')
hiddenimports += collect_submodules('opentele')
hiddenimports += ['windnd']
hiddenimports += collect_submodules('ttkbootstrap')

datas = [('界面文本.txt', '.')]
datas += collect_data_files('ttkbootstrap')

a = Analysis(
    ['tg_ui.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TG工具箱GUI',
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
    name='TG工具箱GUI',
)
