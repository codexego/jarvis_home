# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec para Jarvis Home Desktop."""

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "data"), "data"),
    ],
    hiddenimports=[
        "vosk",
        "sounddevice",
        "pyttsx3",
        "comtypes",
        "comtypes.client",
        "ultralytics",
        "cv2",
        "mss",
        "pyautogui",
        "pyperclip",
        "pytesseract",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "modules",
        "modules.voice",
        "modules.vision",
        "modules.screen",
        "modules.ai",
        "modules.executor",
        "modules.memory",
        "modules.response",
        "desktop",
        "core",
        "services",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="JarvisHome",
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
    manifest=str(ROOT / "jarvis.manifest") if sys.platform == "win32" else None,
)
