# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
import importlib.util

_bin_path = os.path.join(ROOT, "packaging", "alphaloop_pyinstaller_binaries.py")
_bin_spec = importlib.util.spec_from_file_location(
    "alphaloop_pyinstaller_binaries", _bin_path
)
_bin_mod = importlib.util.module_from_spec(_bin_spec)
assert _bin_spec.loader is not None
_bin_spec.loader.exec_module(_bin_mod)

hidden = collect_submodules("engine")
akshare_datas = collect_data_files("akshare")
analysis = Analysis(
    [os.path.join(ROOT, "engine", "main.py")],
    pathex=[ROOT],
    binaries=_bin_mod.collect_py_mini_racer_binaries(),
    datas=[
        (os.path.join(ROOT, "contracts"), "contracts"),
        (
            os.path.join(ROOT, "engine", "research", "symbol_pools"),
            "engine/research/symbol_pools",
        ),
        (
            os.path.join(ROOT, "engine", "research", "data", "en_common_words.txt"),
            "engine/research/data",
        ),
    ]
    + akshare_datas,
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
