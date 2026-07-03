"""Windows 한글 경로에서 OpenCV XML 로드 오류 방지."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import cv2

_CASCADE_CACHE: Path | None = None


def get_face_cascade() -> cv2.CascadeClassifier:
    """OpenCV C++는 Windows에서 비ASCII 경로 XML을 읽지 못해 temp 경로 사용."""
    global _CASCADE_CACHE

    if _CASCADE_CACHE is None:
        source = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        tmp = Path(tempfile.gettempdir()) / "emotionai_haarcascade_frontalface.xml"
        if source.exists() and (not tmp.exists() or tmp.stat().st_size != source.stat().st_size):
            shutil.copy2(source, tmp)
        _CASCADE_CACHE = tmp

    cascade = cv2.CascadeClassifier(str(_CASCADE_CACHE))
    if cascade.empty():
        raise RuntimeError("얼굴 검출 모델(haarcascade)을 로드할 수 없습니다.")
    return cascade
