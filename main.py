"""
Jarvis Home - Punto de entrada principal.

Uso:
  python main.py              # modo consola 24/7
  python main.py --desktop      # aplicación de escritorio
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jarvis Home")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Iniciar aplicación de escritorio (UI completa)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Ejecutable empaquetado → siempre modo escritorio
    if getattr(sys, "frozen", False):
        args.desktop = True

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if args.desktop:
        from desktop.app import run_desktop

        run_desktop()
        return

    from core.app import JarvisApp
    from core.bootstrap import build_registry

    async def _run() -> None:
        log_dir = Path(__file__).parent / "logs"
        app = JarvisApp(
            registry=build_registry(desktop_mode=False),
            log_file=log_dir / "jarvis.log",
        )
        try:
            await app.run_forever()
        except KeyboardInterrupt:
            await app.stop()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
