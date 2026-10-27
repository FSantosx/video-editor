"""Teste de ponta a ponta: upload -> análise -> render -> edição -> re-render.

Usa um vídeo sintético (lavfi) e TRANSCRIBER=sidecar, então não precisa do modelo do Whisper.
"""
import importlib
import json
import subprocess
import time

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    duration = 50
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
    sidecar = tmp_path / "words.json"
    sidecar.write_text(json.dumps(words))

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRANSCRIBER", "sidecar")
    monkeypatch.setenv("SIDECAR_WORDS", str(sidecar))
    monkeypatch.setenv("API_KEY", "k")
    monkeypatch.setenv("X264_PRESET", "ultrafast")
    from app import config, jobs, main, store
    for mod in (config, store, jobs, main):
        importlib.reload(mod)

    from fastapi.testclient import TestClient
    with TestClient(main.app, headers={"X-API-Key": "k"}) as c:
        c.video_path = video
        yield c


def wait(client, vid, cond, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        v = client.get(f"/videos/{vid}").json()
        if v["status"] == "error":
            pytest.fail(v["error"])
        if cond(v):
            return v
        time.sleep(0.5)
    pytest.fail(f"timeout: {v}")


def test_full_flow(client):
    assert client.get("/videos", headers={"X-API-Key": "errada"}).status_code == 401

    with open(client.video_path, "rb") as f:
        r = client.post("/videos", files={"file": ("in.mp4", f, "video/mp4")})
    assert r.status_code == 201
    vid = r.json()["id"]

    done = lambda v: v["shorts"] and all(s["render"]["status"] == "done" for s in v["shorts"])
    v = wait(client, vid, done)
    assert v["meta"]["width"] == 640
    short = v["shorts"][0]
    assert 30 <= short["duration"] <= 61
    assert short["reframe"]["mode"] == "blur"  # testsrc não tem rosto

    r = client.get(f"/videos/{vid}/shorts/1/video")
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4"

    r = client.patch(f"/videos/{vid}/shorts/1",
                     json={"start": 5, "end": 40, "title": "Novo", "crop_center": 0.3})
    assert r.status_code == 200
    v = wait(client, vid, lambda v: v["shorts"][0]["render"]["status"] == "done"
             and v["shorts"][0]["render"]["version"] == 2)
    s = v["shorts"][0]
    assert s["title"] == "Novo"
    assert s["reframe"] == {"mode": "crop", "centers": [0.3] * len(s["clips"]), "manual": True}

    assert client.patch(f"/videos/{vid}/shorts/1", json={"start": 30, "end": 10}).status_code == 422
    assert client.delete(f"/videos/{vid}").status_code == 204
    assert client.get(f"/videos/{vid}").status_code == 404
