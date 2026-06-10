"""Descarga modelo VOSK en español (o inglés como fallback)."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

MODELS = {
    "es": {
        "name": "vosk-model-small-es-0.42",
        "url": "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip",
    },
    "en": {
        "name": "vosk-model-small-en-us-0.15",
        "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    },
}


def download_model(lang: str = "es") -> int:
    spec = MODELS.get(lang, MODELS["es"])
    root = Path(__file__).resolve().parents[1]
    models_dir = root / "models"
    target = models_dir / spec["name"]

    if target.is_dir():
        print(f"Modelo ya existe: {target}")
        return 0

    models_dir.mkdir(parents=True, exist_ok=True)
    archive = models_dir / f"{spec['name']}.zip"

    print(f"Descargando {spec['url']} ...")
    urlretrieve(spec["url"], archive)

    print("Extrayendo...")
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(models_dir)

    archive.unlink(missing_ok=True)
    print(f"Listo: {target}")
    return 0


def main() -> int:
    lang = sys.argv[1] if len(sys.argv) > 1 else "es"
    try:
        return download_model(lang)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if lang == "es":
            print("Intentando modelo inglés como fallback...")
            return download_model("en")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
