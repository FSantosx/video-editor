"""Reenquadramento para a proporção de saída (9:16, 1:1).

Para cada clip, amostra alguns frames, detecta rostos e guarda o centro X
(0 a 1) do rosto principal. Um centro fixo por clip mantém a imagem estável
e a troca acontece no corte seco, que já existe por causa das pausas.

Modos resultantes:
  "fit"  - vídeo já está na proporção de saída: só escala
  "crop" - recorte seguindo o rosto (ou vertical, se o original for mais alto que a saída)
  "blur" - nenhum rosto achado: vídeo inteiro centralizado sobre fundo desfocado
"""
import subprocess
from pathlib import Path

import cv2
import numpy as np

SAMPLES_PER_SECOND = 2
MAX_SAMPLES_PER_CLIP = 6
DETECT_WIDTH = 960
# O Haar dá falso positivo em ~4% dos frames sem rosto (texturas, gráficos): só
# considera que há rosto se ele aparecer em pelo menos esta fração das amostras
MIN_FACE_RATIO = 0.2


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


def compute_reframe(source: Path, clips: list[dict], width: int, height: int,
                    target_aspect: float = 9 / 16) -> dict:
    src_aspect = width / height
    if abs(src_aspect - target_aspect) / target_aspect < 0.02:
        return {"mode": "fit", "centers": []}  # já está na proporção certa
    if src_aspect < target_aspect:
        # Original mais "em pé" que a saída (ex.: celular -> 1:1): recorte vertical, sem rosto
        return {"mode": "crop", "centers": [0.5] * len(clips)}

    read_frame, close = _frame_reader(source, width, height)
    detector = _detector()
    centers: list[float | None] = []
    samples = hits = 0
    try:
        for c in clips:
            dur = c["out"] - c["in"]
            n = int(np.clip(round(dur * SAMPLES_PER_SECOND), 1, MAX_SAMPLES_PER_CLIP))
            found = []
            for t in np.linspace(c["in"], c["out"], n + 2)[1:-1]:
                frame = read_frame(float(t))
                if frame is None:
                    continue
                samples += 1
                if (cx := _face_center(frame, detector)) is not None:
                    found.append(cx)
                    hits += 1
            centers.append(float(np.median(found)) if found else None)
    finally:
        close()

    known = [c for c in centers if c is not None]
    if not known or hits < max(2, MIN_FACE_RATIO * samples):  # poucos acertos = falso positivo
        return {"mode": "blur", "centers": []}
    # clip sem rosto herda o vizinho anterior (ou o primeiro conhecido)
    filled, last = [], known[0]
    for c in centers:
        last = c if c is not None else last
        filled.append(round(last, 4))
    return {"mode": "crop", "centers": filled}


def _frame_reader(source: Path, width: int, height: int):
    """Lê um frame no tempo t (s). Usa o OpenCV; se ele não abrir o arquivo
    (no Windows isso acontece com caminhos acentuados, ex. C:\\Users\\Fábio),
    extrai o frame com o ffmpeg, que lida com qualquer caminho."""
    cap = cv2.VideoCapture(str(source))
    if cap.isOpened():
        def read_cv(t: float):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            return frame if ok else None
        return read_cv, cap.release

    cap.release()
    w = min(width, DETECT_WIDTH) // 2 * 2
    h = int(round(height * w / width)) // 2 * 2

    def read_ffmpeg(t: float):
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(source), "-frames:v", "1",
             "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"],
            capture_output=True)
        if proc.returncode != 0 or len(proc.stdout) != w * h * 3:
            return None
        return np.frombuffer(proc.stdout, dtype=np.uint8).reshape(h, w, 3)

    return read_ffmpeg, lambda: None
