"""Análisis de pantalla: texto, botones y detección de video."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np

from services.logging_service import get_logger

logger = get_logger("screen_analyzer")

_YOUTUBE_HINTS = ("youtube", "youtu.be", "watch?v=", "suscribirse", "suscripción")
_PLAY_WORDS = ("play", "reproducir", "reproduce", "pause", "pausa", "reanudar", "continuar")
_SEARCH_HINTS = ("search", "buscar", "busca", "búsqueda", "busqueda")


@dataclass(slots=True)
class UIElement:
    type: str  # button, text, video, search_box
    label: str
    bbox: list[int]  # x, y, w, h relativo al frame analizado
    confidence: float = 0.0
    center: list[int] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.center is None:
            x, y, w, h = self.bbox
            data["center"] = [x + w // 2, y + h // 2]
        return data


class ScreenAnalyzer:
    """Extrae texto y elementos UI de una captura de pantalla."""

    def __init__(
        self,
        analysis_scale: float = 0.6,
        ocr_min_confidence: int = 40,
        ocr_lang: str = "spa+eng",
    ) -> None:
        self.analysis_scale = analysis_scale
        self.ocr_min_confidence = ocr_min_confidence
        self.ocr_lang = ocr_lang
        self._ocr_available: bool | None = None

    def analyze(
        self,
        frame_bgr: np.ndarray,
        search_phrase: str | None = None,
    ) -> dict[str, Any]:
        scaled, scale = self._resize(frame_bgr)
        text_elements, text_lines = self._extract_text(scaled)
        buttons = self._detect_buttons(scaled)
        video_elements = self._detect_youtube(scaled, text_lines, text_elements)
        search_boxes = self._detect_search_boxes(text_elements, frame)

        elements = [e.to_dict() for e in text_elements + buttons + video_elements + search_boxes]
        has_youtube = any(e.type == "video" for e in video_elements)
        play_target = self._find_play_target(buttons, video_elements, text_elements)

        video_titles = self._extract_video_titles(text_lines, text_elements)
        phrase_match = None
        if search_phrase:
            phrase_match = self._find_phrase_match(text_lines, search_phrase, video_titles)

        context = {
            "summary": self._build_summary(text_lines, elements),
            "has_youtube": has_youtube,
            "text_line_count": len(text_lines),
            "button_count": len(buttons),
            "search_phrase": search_phrase,
            "phrase_match": phrase_match,
            "play_target": play_target.to_dict() if play_target else None,
            "video_titles": video_titles,
            "youtube_search_box": search_boxes[0].to_dict() if search_boxes else None,
            "scale": scale,
        }

        return {
            "elements": elements,
            "text_lines": text_lines,
            "context": context,
        }

    def _resize(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        if self.analysis_scale >= 1.0:
            return frame, 1.0
        scaled = cv2.resize(
            frame,
            None,
            fx=self.analysis_scale,
            fy=self.analysis_scale,
            interpolation=cv2.INTER_AREA,
        )
        return scaled, self.analysis_scale

    def _ocr_enabled(self) -> bool:
        if self._ocr_available is not None:
            return self._ocr_available
        try:
            import pytesseract  # noqa: F401

            self._ocr_available = True
        except ImportError:
            self._ocr_available = False
            logger.warning("pytesseract no instalado; detección de texto limitada")
        return self._ocr_available

    def _extract_text(
        self, frame: np.ndarray
    ) -> tuple[list[UIElement], list[str]]:
        if not self._ocr_enabled():
            return [], []

        import pytesseract

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        data = pytesseract.image_to_data(
            rgb,
            lang=self.ocr_lang,
            output_type=pytesseract.Output.DICT,
        )

        elements: list[UIElement] = []
        lines: dict[tuple[int, int, int], list[str]] = {}

        n = len(data["text"])
        for i in range(n):
            text = (data["text"][i] or "").strip()
            conf = int(float(data["conf"][i])) if data["conf"][i] != "-1" else 0
            if not text or conf < self.ocr_min_confidence:
                continue

            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            elements.append(
                UIElement(type="text", label=text, bbox=[x, y, w, h], confidence=conf / 100)
            )
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(text)

        text_lines = [" ".join(words) for words in lines.values()]
        return elements, text_lines

    def _detect_buttons(self, frame: np.ndarray) -> list[UIElement]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        buttons: list[UIElement] = []
        h_img, w_img = frame.shape[:2]

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area < 800 or area > w_img * h_img * 0.08:
                continue
            aspect = w / max(h, 1)
            if not (1.5 <= aspect <= 8.0) or not (18 <= h <= 90):
                continue
            roi = gray[y : y + h, x : x + w]
            if roi.size == 0:
                continue
            std = float(np.std(roi))
            if std < 12:
                continue
            buttons.append(
                UIElement(
                    type="button",
                    label="button",
                    bbox=[x, y, w, h],
                    confidence=0.55,
                )
            )

        buttons.sort(key=lambda b: b.bbox[2] * b.bbox[3], reverse=True)
        return buttons[:25]

    def _detect_youtube(
        self,
        frame: np.ndarray,
        text_lines: list[str],
        text_elements: list[UIElement],
    ) -> list[UIElement]:
        elements: list[UIElement] = []
        joined = " ".join(text_lines).lower()

        if any(hint in joined for hint in _YOUTUBE_HINTS):
            elements.append(
                UIElement(
                    type="video",
                    label="YouTube",
                    bbox=[0, 0, frame.shape[1], frame.shape[0]],
                    confidence=0.7,
                    center=[frame.shape[1] // 2, frame.shape[0] // 2],
                )
            )

        play_region = self._detect_red_play_button(frame)
        if play_region:
            elements.append(
                UIElement(
                    type="video",
                    label="YouTube player",
                    bbox=play_region,
                    confidence=0.75,
                )
            )

        for te in text_elements:
            if te.label.lower() in _PLAY_WORDS:
                elements.append(
                    UIElement(
                        type="button",
                        label=te.label,
                        bbox=te.bbox,
                        confidence=0.65,
                    )
                )

        return elements

    def _detect_red_play_button(self, frame: np.ndarray) -> list[int] | None:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower1 = np.array([0, 120, 70])
        upper1 = np.array([10, 255, 255])
        lower2 = np.array([170, 120, 70])
        upper2 = np.array([180, 255, 255])
        mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h_img, w_img = frame.shape[:2]

        best = None
        best_area = 0
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area < 400 or area > w_img * h_img * 0.15:
                continue
            aspect = w / max(h, 1)
            if 0.7 <= aspect <= 1.8:
                if area > best_area:
                    best_area = area
                    best = [x, y, w, h]
        return best

    def _detect_search_boxes(
        self, text_elements: list[UIElement], frame: np.ndarray
    ) -> list[UIElement]:
        boxes: list[UIElement] = []
        h_img = frame.shape[0]

        for te in text_elements:
            label = te.label.lower()
            if any(h in label for h in _SEARCH_HINTS):
                boxes.append(
                    UIElement(
                        type="search_box",
                        label=te.label,
                        bbox=te.bbox,
                        confidence=0.65,
                    )
                )

        if not boxes and h_img > 0:
            w_img = frame.shape[1]
            boxes.append(
                UIElement(
                    type="search_box",
                    label="YouTube search",
                    bbox=[int(w_img * 0.25), int(h_img * 0.04), int(w_img * 0.5), int(h_img * 0.06)],
                    confidence=0.5,
                )
            )
        return boxes

    @staticmethod
    def _extract_video_titles(
        text_lines: list[str],
        text_elements: list[UIElement],
    ) -> list[dict[str, Any]]:
        titles: list[dict[str, Any]] = []
        skip_words = {"youtube", "buscar", "search", "inicio", "home", "suscribirse"}

        for i, line in enumerate(text_lines):
            lower = line.lower()
            if len(line) < 12 or any(w in lower for w in skip_words):
                continue
            if line.count(" ") >= 2:
                titles.append({"line_index": i, "line": line, "confidence": 0.7})
        return titles[:10]

    @staticmethod
    def _find_play_target(
        buttons: list[UIElement],
        videos: list[UIElement],
        texts: list[UIElement],
    ) -> UIElement | None:
        for te in texts:
            if te.label.lower() in _PLAY_WORDS:
                return te
        if videos:
            for v in videos:
                if v.bbox != [0, 0, 0, 0]:
                    return v
        return buttons[0] if buttons else None

    @staticmethod
    def _find_phrase_match(
        text_lines: list[str],
        phrase: str,
        video_titles: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        phrase_norm = phrase.strip().lower()
        if not phrase_norm:
            return None

        for title in video_titles or []:
            line = title.get("line", "")
            if phrase_norm in line.lower():
                return {
                    "line_index": title.get("line_index"),
                    "line": line,
                    "matched": phrase,
                    "source": "video_title",
                }

        for i, line in enumerate(text_lines):
            if phrase_norm in line.lower():
                return {"line_index": i, "line": line, "matched": phrase, "source": "ocr"}
        return None

    @staticmethod
    def _build_summary(text_lines: list[str], elements: list[dict]) -> str:
        types = {e["type"] for e in elements}
        parts: list[str] = []
        if "video" in types:
            parts.append("video detectado")
        if "button" in types:
            parts.append(f"{sum(1 for e in elements if e['type'] == 'button')} botones")
        if text_lines:
            preview = text_lines[0][:60]
            parts.append(f"texto: {preview}")
        return ", ".join(parts) if parts else "pantalla sin elementos destacados"


def scale_point(x: int, y: int, scale: float, monitor: dict[str, int]) -> tuple[int, int]:
    """Convierte coordenadas del frame escalado a coordenadas absolutas de pantalla."""
    abs_x = monitor["left"] + int(x / scale)
    abs_y = monitor["top"] + int(y / scale)
    return abs_x, abs_y
