# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
hidden = collect_submodules("engine")
akshare_datas = collect_data_files("akshare")
analysis = Analysis(
    [os.path.join(ROOT, "engine", "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "contracts"), "contracts")] + akshare_datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="alphaloop-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
collect = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="alphaloop-engine",
)
