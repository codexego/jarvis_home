"""Detección de objetos con YOLO local (YOLOv8 nano)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from modules.vision.label_map import to_spanish, translate_labels
from services.logging_service import get_logger

if TYPE_CHECKING:
    import numpy as np

logger = get_logger("object_detector")


@dataclass(slots=True)
class DetectedObject:
    label: str
    confidence: float
    bbox: list[int]  # x1, y1, x2, y2 en píxeles

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ObjectDetector:
    """Detector YOLO ligero con carga diferida del modelo."""

    def __init__(
        self,
        model_path: Path,
        model_name: str = "yolov8n.pt",
        confidence: float = 0.45,
        inference_size: int = 320,
    ) -> None:
        self.model_path = model_path
        self.model_name = model_name
        self.confidence = confidence
        self.inference_size = inference_size
        self._model = None

    def _load_model(self) -> None:
        if self._model is not None:
            return

        from ultralytics import YOLO

        source = str(self.model_path) if self.model_path.is_file() else self.model_name
        self._model = YOLO(source)

        if not self.model_path.is_file() and Path(self._model.ckpt_path or "").is_file():
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil

            shutil.copy2(self._model.ckpt_path, self.model_path)

        logger.info("Modelo YOLO cargado: %s", source)

    def detect(self, frame: np.ndarray) -> list[DetectedObject]:
        """Ejecuta detección sobre un frame BGR."""
        self._load_model()
        assert self._model is not None

        results = self._model.predict(
            source=frame,
            imgsz=self.inference_size,
            conf=self.confidence,
            verbose=False,
        )

        detections: list[DetectedObject] = []
        if not results:
            return detections

        result = results[0]
        if result.boxes is None:
            return detections

        names = result.names or {}
        for box in result.boxes:
            cls_id = int(box.cls[0])
            label = names.get(cls_id, str(cls_id))
            conf = float(box.conf[0])
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            detections.append(
                DetectedObject(label=label, confidence=round(conf, 3), bbox=[x1, y1, x2, y2])
            )

        detections.sort(key=lambda d: d.confidence, reverse=True)
        logger.info(
            "Detección completada | objetos=%d | top=%s",
            len(detections),
            detections[0].label if detections else "ninguno",
        )
        return detections

    @staticmethod
    def build_context(
        detections: list[DetectedObject],
        frame_shape: tuple[int, ...] | None = None,
    ) -> dict[str, Any]:
        """Resume detecciones en contexto legible para la IA."""
        if not detections:
            return {
                "summary": "",
                "labels": [],
                "count": 0,
                "primary_object": None,
                "hand_candidates": [],
            }

        labels_en = [d.label for d in detections]
        unique_labels = list(dict.fromkeys(labels_en))
        labels_es = translate_labels(unique_labels)

        hand_candidates = detections
        if frame_shape and len(frame_shape) >= 2:
            h, w = frame_shape[:2]
            cx, cy = w / 2, h * 0.65
            hand_candidates = sorted(
                detections,
                key=lambda d: (
                    ((d.bbox[0] + d.bbox[2]) / 2 - cx) ** 2
                    + ((d.bbox[1] + d.bbox[3]) / 2 - cy) ** 2
                ),
            )

        primary = hand_candidates[0] if hand_candidates else detections[0]

        primary_es = to_spanish(primary.label)
        hand_es = [to_spanish(d.label) for d in hand_candidates[:3]]

        return {
            "summary": ", ".join(labels_es),
            "labels": labels_es,
            "labels_en": unique_labels,
            "count": len(detections),
            "primary_object": primary_es,
            "primary_object_en": primary.label,
            "primary_confidence": primary.confidence,
            "hand_candidates": hand_es,
            "hand_candidates_en": [d.label for d in hand_candidates[:3]],
        }
