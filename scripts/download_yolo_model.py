"""Descarga el modelo YOLOv8 nano para vision_module."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    target = root / "models" / "yolov8n.pt"

    if target.is_file():
        print(f"Modelo ya existe: {target}")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)

    print("Descargando YOLOv8n...")
    from ultralytics import YOLO

    model = YOLO("yolov8n.pt")
    source = Path(model.ckpt_path or "yolov8n.pt")
    if source.is_file():
        import shutil

        shutil.copy2(source, target)
        print(f"Modelo guardado en: {target}")
    else:
        print("Modelo descargado en caché de ultralytics (se usará en el primer arranque)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
