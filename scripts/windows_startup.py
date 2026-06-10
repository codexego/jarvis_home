"""Registro de inicio automático en Windows."""

from __future__ import annotations

import sys
from pathlib import Path

if sys.platform != "win32":
    raise RuntimeError("Solo disponible en Windows")

import winreg  # type: ignore[import-untyped]

_APP_NAME = "JarvisHome"
_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _exe_path() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    main_py = Path(__file__).resolve().parents[1] / "main.py"
    python = Path(sys.executable).resolve()
    return f'"{python}" "{main_py}" --desktop'


def set_startup_enabled(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _exe_path())
        else:
            try:
                winreg.DeleteValue(key, _APP_NAME)
            except FileNotFoundError:
                pass


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except FileNotFoundError:
        return False
