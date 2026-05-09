from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VisionResult:
    enabled: bool
    ok: bool
    message: str
    detections: tuple[str, ...] = ()


def process_image(image_path: str | Path) -> VisionResult:
    """Future integration point for the computer vision module."""
    return VisionResult(
        enabled=False,
        ok=False,
        message=(
            "Module vision non configure. Prochaine etape: brancher ici le "
            "modele de detection sur l'image selectionnee."
        ),
        detections=(str(image_path),),
    )
