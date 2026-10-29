"""Formatos múltiplos (9:16 + 1:1), sincronização entre formatos e modo desktop."""
import importlib
import json
import subprocess
import time

import pytest

from app.pipeline.render import crop_box


def test_crop_box_horizontal_source():
    # 1920x1080 -> 9:16 corta nas laterais seguindo o rosto
    assert crop_box(1920, 1080, 1080, 1920, 0.5) == (606, 1080, 656, 0)
    # 1:1: quadrado de 1080 encostado na borda quando o rosto está no canto
    assert crop_box(1920, 1080, 1080, 1080, 0.0) == (1080, 1080, 0, 0)
    assert crop_box(1920, 1080, 1080, 1080, 1.0) == (1080, 1080, 840, 0)


def test_crop_box_vertical_source_to_square():
    # vídeo de celular 1080x1920 -> 1:1 corta em cima/embaixo, mirando o terço de cima
    cw, ch, x, y = crop_box(1080, 1920, 1080, 1080, 0.5)
    assert (cw, ch, x) == (1080, 1080, 0)
    assert 0 < y < 1920 - 1080


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return s["width"], s["height"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    duration = 45
    video = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"testsrc2=s=640x360:r=30:d={duration}",
                    "-f", "lavfi", "-i", f"sine=f=220:d={duration}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest",
                    str(video)], check=True)
    words, t = [], 0.5
    while t < duration - 1:
        words.append({"word": "palavra." if len(words) % 8 == 7 else "palavra",
                      "start": round(t, 2), "end": round(t + 0.3, 2)})
        t += 0.4
    (tmp_path / "words.json").write_text(json.dumps(words))
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>interface</h1>")

    for k, v in {"DATA_DIR": tmp_path / "data", "TRANSCRIBER": "sidecar",
                 "SIDECAR_WORDS": tmp_path / "words.json", "API_KEY": "",
                 "X264_PRESET": "ultrafast", "FORMATS": "9:16,1:1",
                 "VIDEO_ENCODER": "auto", "DESKTOP_MODE": "1", "WEB_DIR": web,
                 "MAX_SHORTS": "1"}.items():
        monkeypatch.setenv(k, str(v))
    from app import config, jobs, main, store
    from app.pipeline import render
    for mod in (config, store, render, jobs, main):
        importlib.reload(mod)

    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        c.video_path = video
        c.store = store
        yield c


def wait_done(client, vid, version=1, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        v = client.get(f"/videos/{vid}").json()
        assert v["status"] != "error", v["error"]
        if v["shorts"] and all(s["render"]["status"] == "done" and s["render"]["version"] >= version
                               for s in v["shorts"]):
            return v
        time.sleep(0.5)
    pytest.fail("timeout")


def test_two_formats_per_clip_and_group_sync(client):
    assert client.get("/").text == "<h1>interface</h1>"  # interface servida na raiz
    system = client.get("/system").json()
    assert system["formats"] == ["9:16", "1:1"]
    assert system["video_encoder"] in ("libx264", "h264_nvenc")

    with open(client.video_path, "rb") as f:
        vid = client.post("/videos", files={"file": ("in.mp4", f, "video/mp4")}).json()["id"]
    v = wait_done(client, vid)

    shorts = v["shorts"]
    assert [s["format"] for s in shorts] == ["9:16", "1:1"]
    assert shorts[0]["group"] == shorts[1]["group"]
    shorts_dir = client.store.video_dir(vid) / "shorts"
    assert probe(shorts_dir / shorts[0]["render"]["file"]) == (1080, 1920)
    assert probe(shorts_dir / shorts[1]["render"]["file"]) == (1080, 1080)

    r = client.get(f"/videos/{vid}/shorts/{shorts[1]['id']}/video")
    assert "corte_1_1x1.mp4" in r.headers["content-disposition"]

    # editar o 9:16 com sync_group atualiza e re-renderiza o 1:1 também
    r = client.patch(f"/videos/{vid}/shorts/{shorts[0]['id']}",
                     json={"title": "Mesmo título", "start": 2, "end": 38, "sync_group": True})
    assert r.status_code == 200
    v = wait_done(client, vid, version=2)
    assert {s["title"] for s in v["shorts"]} == {"Mesmo título"}
    assert v["shorts"][0]["clips"] == v["shorts"][1]["clips"]

    # versões antigas apagadas: só sobra o MP4 da versão atual de cada short
    mp4s = sorted(p.name for p in shorts_dir.glob("*.mp4"))
    assert mp4s == sorted(s["render"]["file"] for s in v["shorts"])
    assert all("_v2" in name for name in mp4s)


def test_open_folder_only_in_desktop_mode(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DESKTOP_MODE", False)
    assert client.post("/videos/abc/open-folder").status_code == 404


def test_reframe_falls_back_to_ffmpeg_when_opencv_cannot_open(tmp_path, monkeypatch):
    """No Windows o OpenCV não abre caminhos acentuados; o ffmpeg deve assumir."""
    from app.pipeline import reframe

    video = tmp_path / "vídeo.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:d=3",
                    "-c:v", "libx264", "-preset", "ultrafast", str(video)], check=True)
    calls = []

    class Closed:
        def __init__(self, *_):
            pass

        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr(reframe.cv2, "VideoCapture", Closed)
    monkeypatch.setattr(reframe, "_face_center", lambda frame, _: calls.append(frame.shape) or None)
    result = reframe.compute_reframe(video, [{"in": 0.5, "out": 2.5}], 640, 360)
    assert calls and calls[0] == (360, 640, 3)  # frames chegaram via ffmpeg
    assert result["mode"] == "blur"  # testsrc não tem rosto


def test_teaser_toggle_via_patch(client):
    with open(client.video_path, "rb") as f:
        vid = client.post("/videos", files={"file": ("in.mp4", f, "video/mp4")}).json()["id"]
    v = wait_done(client, vid)
    s = v["shorts"][0]
    assert s["teaser"]["enabled"] and s["teaser"]["clips"]
    with_teaser = s["duration"]
    teaser_len = sum(c["out"] - c["in"] for c in s["teaser"]["clips"])

    r = client.patch(f"/videos/{vid}/shorts/{s['id']}", json={"teaser": False, "sync_group": True})
    assert r.status_code == 200
    v = wait_done(client, vid, version=2)
    for short in v["shorts"]:
        assert not short["teaser"]["enabled"]
        assert abs(short["duration"] - (with_teaser - teaser_len)) < 0.01
        if short["reframe"]["mode"] == "crop":  # um centro por clip renderizado
            assert len(short["reframe"]["centers"]) == len(short["clips"])
    shorts_dir = client.store.video_dir(vid) / "shorts"
    real = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(shorts_dir / v["shorts"][0]["render"]["file"])],
                                capture_output=True, text=True).stdout)
    assert abs(real - v["shorts"][0]["duration"]) < 0.6
