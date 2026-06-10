"""Seguimiento corto de objetos (burst bajo demanda)."""

from __future__ import annotations

from typing import Any

from modules.vision.object_detector import DetectedObject, ObjectDetector


def _iou(a: list[int], b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class ShortBurstTracker:
    """
    Captura varios frames en ráfaga y consolida detecciones.

    Solo se activa bajo demanda para no consumir CPU constantemente.
    """

    def __init__(
        self,
        detector: ObjectDetector,
        camera,
        frames: int = 4,
        interval_s: float = 0.35,
    ) -> None:
        self._detector = detector
        self._camera = camera
        self.frames = frames
        self.interval_s = interval_s

    def capture_and_track(self) -> dict[str, Any]:
        all_detections: list[DetectedObject] = []
        last_shape = None

        frames = self._camera.capture_burst(self.frames, self.interval_s)
        for frame in frames:
            last_shape = frame.shape
            dets = self._detector.detect(frame)
            all_detections.extend(dets)

        merged = self._merge_detections(all_detections)
        context = ObjectDetector.build_context(merged, last_shape)
        context["tracking_frames"] = self.frames
        context["labels_es"] = [d.label for d in merged]

        return {
            "objects": [d.to_dict() for d in merged],
            "context": context,
            "frame_shape": list(last_shape) if last_shape is not None else None,
        }

    def _merge_detections(self, detections: list[DetectedObject]) -> list[DetectedObject]:
        if not detections:
            return []

        clusters: list[list[DetectedObject]] = []
        for det in detections:
            placed = False
            for cluster in clusters:
                if _iou(det.bbox, cluster[0].bbox) >= 0.3 and det.label == cluster[0].label:
                    cluster.append(det)
                    placed = True
                    break
            if not placed:
                clusters.append([det])

        merged: list[DetectedObject] = []
        for cluster in clusters:
            best = max(cluster, key=lambda d: d.confidence)
            avg_conf = sum(d.confidence for d in cluster) / len(cluster)
            merged.append(
                DetectedObject(
                    label=best.label,
                    confidence=round(avg_conf, 3),
                    bbox=best.bbox,
                )
            )
        merged.sort(key=lambda d: d.confidence, reverse=True)
        return merged
