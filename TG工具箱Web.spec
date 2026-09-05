# -*- mode: python ; coding: utf-8 -*-
# TG工具箱 Web 版打包配置 (PyInstaller onedir)
# 用法: python -m PyInstaller TG工具箱Web.spec
# 产物: dist/TG工具箱Web/TG工具箱Web.exe (pywebview + FastAPI + Svelte 前端)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
hiddenimports += collect_submodules('telethon')
hiddenimports += collect_submodules('openpyxl')
hiddenimports += collect_submodules('opentele')
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('pywebview')
hiddenimports += collect_submodules('websockets')
hiddenimports += collect_submodules('starlette')
hiddenimports += collect_submodules('qrcode')
# PIL 不做全量收集: 源码无直接使用,仅 qrcode 间接依赖,
# PyInstaller 官方 Pillow hook 会按需收集(全量收集约多占 10MB)
hiddenimports += collect_submodules('cryptography')
hiddenimports += collect_submodules('cbor2')
hiddenimports += collect_submodules('bleak')
hiddenimports += collect_submodules('winrt')

datas = [('界面文本.txt', '.')]
datas += [('webapp/dist', 'webapp/dist')]
datas += collect_data_files('pywebview')
# opentele 非代码数据文件(devices.json 等): tdata 转换必需,缺失报
# "[Errno 2] No such file or directory: ..._internal\opentele\devices.json"
datas += collect_data_files('opentele')

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
              'PyQt5.QtWidgets', 'PyQt5.QtNetwork', 'sip',
              'watchfiles',   # uvicorn 仅 reload 模式使用,运行时不需要
              'PIL'],         # 二维码用纯 zlib PNG 编码,不需要 Pillow(省约 13MB)
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
