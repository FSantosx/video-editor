"""Reenquadramento 16:9 -> 9:16.

Para cada clip, amostra alguns frames, detecta rostos e guarda o centro X
(0 a 1) do rosto principal. Um centro fixo por clip mantém a imagem estável
e a troca acontece no corte seco, que já existe por causa das pausas.

Modos resultantes:
  "fit"  - vídeo já é vertical: só escala
  "crop" - recorte vertical seguindo o rosto
  "blur" - nenhum rosto achado: vídeo inteiro centralizado sobre fundo desfocado
"""
from pathlib import Path

import cv2
import numpy as np

SAMPLES_PER_SECOND = 2
MAX_SAMPLES_PER_CLIP = 6
DETECT_WIDTH = 960


def _detector():
    path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    return cv2.CascadeClassifier(str(path))


def _face_center(frame, detector) -> float | None:
    h, w = frame.shape[:2]
    scale = DETECT_WIDTH / w if w > DETECT_WIDTH else 1.0
    small = cv2.resize(frame, None, fx=scale, fy=scale) if scale != 1.0 else frame
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)  # equalizeHist piorava a detecção
    min_side = max(24, int(small.shape[0] * 0.05))
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6,
                                      minSize=(min_side, min_side))
    if len(faces) == 0:
        return None
    x, _, fw, _ = max(faces, key=lambda f: f[2] * f[3])  # maior rosto = mais perto
    return float((x + fw / 2) / small.shape[1])


def compute_reframe(source: Path, clips: list[dict], width: int, height: int) -> dict:
    if width / height <= 9 / 16 + 0.01:
        return {"mode": "fit", "centers": []}

    cap = cv2.VideoCapture(str(source))
    detector = _detector()
    centers: list[float | None] = []
    try:
        for c in clips:
            dur = c["out"] - c["in"]
            n = int(np.clip(round(dur * SAMPLES_PER_SECOND), 1, MAX_SAMPLES_PER_CLIP))
            found = []
            for t in np.linspace(c["in"], c["out"], n + 2)[1:-1]:
                cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000)
                ok, frame = cap.read()
                if ok and (cx := _face_center(frame, detector)) is not None:
                    found.append(cx)
            centers.append(float(np.median(found)) if found else None)
    finally:
        cap.release()

    known = [c for c in centers if c is not None]
    if not known:
        return {"mode": "blur", "centers": []}
    # clip sem rosto herda o vizinho anterior (ou o primeiro conhecido)
    filled, last = [], known[0]
    for c in centers:
        last = c if c is not None else last
        filled.append(round(last, 4))
    return {"mode": "crop", "centers": filled}
