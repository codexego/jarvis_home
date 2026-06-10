"""Motor de ejecución de acciones con pyautogui y subprocess."""

from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from typing import Any

from services.logging_service import get_logger

logger = get_logger("action_runner")


class ActionRunner:
    """Ejecuta acciones de ratón, teclado y sistema."""

    def __init__(self, action_pause_s: float = 0.04, browser_cmd: str | None = None) -> None:
        self.action_pause_s = action_pause_s
        self.browser_cmd = browser_cmd
        self._pag = None

    def _get_pag(self):
        if self._pag is None:
            import pyautogui

            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = self.action_pause_s
            self._pag = pyautogui
        return self._pag

    def run(self, actions: list[dict[str, Any]], dry_run: bool = False) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for action in actions:
            kind = action.get("type", "unknown")
            try:
                if dry_run:
                    results.append({"type": kind, "ok": True, "dry_run": True, **action})
                    continue
                result = self._execute_one(action)
                results.append(result)
            except Exception as exc:
                logger.exception("Error en accion %s", kind)
                results.append({"type": kind, "ok": False, "error": str(exc)})
        return results

    def _execute_one(self, action: dict[str, Any]) -> dict[str, Any]:
        kind = action.get("type")
        pag = self._get_pag()

        if kind == "click":
            pag.click(
                action["x"],
                action["y"],
                clicks=action.get("clicks", 1),
                button=action.get("button", "left"),
            )
            return {"type": "click", "ok": True, **action}

        if kind == "press":
            pag.press(action["key"])
            return {"type": "press", "ok": True, "key": action["key"]}

        if kind == "hotkey":
            keys = action.get("keys") or []
            pag.hotkey(*keys)
            return {"type": "hotkey", "ok": True, "keys": keys}

        if kind == "type":
            pag.write(action.get("text", ""), interval=action.get("interval", 0.02))
            return {"type": "type", "ok": True, "text": action.get("text", "")}

        if kind in ("type_code", "paste"):
            text = action.get("text", "")
            self._paste_text(text)
            return {"type": kind, "ok": True, "chars": len(text)}

        if kind == "wait":
            time.sleep(float(action.get("seconds", 0.5)))
            return {"type": "wait", "ok": True, "seconds": action.get("seconds")}

        if kind == "open_url":
            url = action["url"]
            if self.browser_cmd:
                subprocess.Popen(self.browser_cmd.split() + [url], shell=False)
            else:
                webbrowser.open(url)
            return {"type": "open_url", "ok": True, "url": url}

        if kind == "open_app":
            cmd = action.get("command") or action.get("app", "")
            return self._launch_app(cmd, action.get("app"))

        if kind == "resume_video":
            pag.press("space")
            return {"type": "resume_video", "ok": True}

        if kind == "play_video":
            key = action.get("key", "space")
            pag.press(key)
            return {"type": "play_video", "ok": True}

        if kind == "shell":
            cmd = action.get("command", "")
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=action.get("timeout", 30),
            )
            return {
                "type": "shell",
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[:500],
            }

        return {"type": kind, "ok": False, "error": "unknown_action"}

    def _launch_app(self, command: str, app_name: str | None = None) -> dict[str, Any]:
        if sys.platform == "win32":
            if " " not in command and not command.startswith("open"):
                subprocess.Popen(["cmd", "/c", "start", "", command], shell=False)
            else:
                subprocess.Popen(command, shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(command, shell=True)
        else:
            subprocess.Popen(command.split(), shell=False)
        logger.info("App lanzada: %s", app_name or command)
        return {"type": "open_app", "ok": True, "app": app_name, "command": command}

    def _paste_text(self, text: str) -> None:
        pag = self._get_pag()
        if not text:
            return
        try:
            import pyperclip

            pyperclip.copy(text)
            pag.hotkey("ctrl", "v")
            return
        except ImportError:
            pass

        if sys.platform == "win32":
            subprocess.run(
                ["powershell", "-command", f"Set-Clipboard -Value {repr(text)}"],
                check=True,
                capture_output=True,
            )
            pag.hotkey("ctrl", "v")
        else:
            pag.write(text, interval=0.01)
