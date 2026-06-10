"""Construye el ejecutable Windows con PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    spec = root / "jarvis.spec"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec),
        "--noconfirm",
        "--clean",
    ]
    print("Construyendo:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=root)
    if result.returncode == 0:
        dist = root / "dist" / "JarvisHome.exe"
        print(f"\n✓ Ejecutable listo: {dist}")
        print("  Ejecuta como administrador para control total del sistema.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
