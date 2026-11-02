"""Fila de publicação, horários, metadados e integração com o YouTube (Google simulado)."""
import importlib
import json
import subprocess
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app import config
from app.publish import queue


# ---------------------------------------------------------------- horários

def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_next_slots_in_brasilia_time():
    # 13h em Brasília (16h UTC): próximos são 18h e 21h de hoje, 12h de amanhã
    got = queue.next_free_slots(4, set(), ["12:00", "18:00", "21:00"], now=utc(2026, 11, 1, 16))
    assert [queue.iso(d) for d in got] == [
        "2026-11-01T21:00:00Z", "2026-11-02T00:00:00Z",
        "2026-11-02T15:00:00Z", "2026-11-02T21:00:00Z"]


def test_next_slots_skip_taken_and_respect_lead_time():
    # 17h50 em Brasília: 18h está a menos de 20 min -> pula; 21h já ocupado -> pula
    got = queue.next_free_slots(1, {"2026-11-02T00:00:00Z"}, ["12:00", "18:00", "21:00"],
                                now=utc(2026, 11, 1, 20, 50))
    assert queue.iso(got[0]) == "2026-11-02T15:00:00Z"


def test_invalid_slots_rejected():
    for bad in (["25:00"], ["12h"], []):
        with pytest.raises(ValueError):
            queue.parse_slots(bad)


def test_metadata_is_ready_for_youtube():
    short = {"title": "O <erro> " + "x" * 200, "text": "A campanha errou feio. A campanha "
             "confiou demais nas pesquisas e a campanha perdeu.", "cta": {"text": "Comenta aí!"}}
    meta = queue.build_metadata(short, {})
    assert len(meta["title"]) <= queue.TITLE_MAX and "<" not in meta["title"]
    assert "#shorts" in meta["description"] and "Comenta aí!" in meta["description"]
    assert meta["tags"][0] == "campanha"  # palavra mais frequente


# ---------------------------------------------------------------- API

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
    (tmp_path / "words.json").write_text(json.dumps(words))
    for k, v in {"DATA_DIR": tmp_path / "data", "TRANSCRIBER": "sidecar",
                 "SIDECAR_WORDS": tmp_path / "words.json", "API_KEY": "k",
                 "X264_PRESET": "ultrafast", "FORMATS": "9:16", "MAX_SHORTS": "2",
                 "SHORT_MIN_S": "10", "SHORT_TARGET_S": "15", "SHORT_MAX_S": "20",
                 "GOOGLE_CLIENT_ID": "cid.apps.googleusercontent.com",
                 "GOOGLE_CLIENT_SECRET": "segredo", "PUBLIC_URL": "https://editor.example",
                 "YOUTUBE_AUDITED": "0"}.items():
        monkeypatch.setenv(k, str(v))
    from app import jobs, main, store
    from app.publish import queue as q, routes, youtube
    for mod in (config, store, q, youtube, jobs, routes, main):
        importlib.reload(mod)

    from fastapi.testclient import TestClient
    with TestClient(main.app, headers={"X-API-Key": "k"}) as c:
        with open(video, "rb") as f:
            vid = c.post("/videos", files={"file": ("in.mp4", f, "video/mp4")}).json()["id"]
        end = time.time() + 600
        while time.time() < end:
            v = c.get(f"/videos/{vid}").json()
            if v["status"] == "ready" and v["shorts"] and all(
                    s["render"]["status"] == "done" for s in v["shorts"]):
                break
            time.sleep(0.5)
        c.vid, c.shorts = vid, v["shorts"]
        c.youtube = youtube
        yield c


def wait_item(client, item_id, statuses, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        item = next(i for i in client.get("/publish/queue").json() if i["id"] == item_id)
        if item["status"] in statuses:
            return item
        time.sleep(0.2)
    pytest.fail(f"item ficou em {item['status']}: {item.get('error')}")


def test_schedule_all_shorts_in_free_slots_assisted(client):
    assert client.get("/publish/queue", headers={"X-API-Key": "x"}).status_code == 401
    settings = client.get("/publish/settings").json()
    assert settings["slots"] == ["12:00", "18:00", "21:00"]
    assert settings["youtube"]["connected"] is False and len(settings["next_slots"]) == 3

    r = client.post("/publish/queue", json={"video_id": client.vid})
    assert r.status_code == 201
    items = r.json()
    assert len(items) == len(client.shorts) >= 1
    assert [i["slot_at"] for i in items] == settings["next_slots"][:len(items)]
    assert all(i["mode"] == "assisted" and i["status"] == "scheduled" for i in items)
    assert "#shorts" in items[0]["description"]

    # o mesmo corte não entra duas vezes
    again = client.post("/publish/queue", json={"video_id": client.vid,
                                                "short_ids": [items[0]["short_id"]]})
    assert again.status_code == 422

    # remarcar, editar título e marcar como postado
    item = items[0]
    r = client.patch(f"/publish/queue/{item['id']}",
                     json={"slot_at": "2030-01-01T15:00:00Z", "title": "Novo título"})
    assert r.json()["slot_at"] == "2030-01-01T15:00:00Z" and r.json()["title"] == "Novo título"
    assert client.patch(f"/publish/queue/{item['id']}",
                        json={"slot_at": "2020-01-01T15:00:00Z"}).status_code == 422
    r = client.patch(f"/publish/queue/{item['id']}", json={"status": "posted"})
    assert r.json()["status"] == "posted" and r.json()["posted_at"]
    assert client.delete(f"/publish/queue/{item['id']}").status_code == 204
    assert all(i["id"] != item["id"] for i in client.get("/publish/queue").json())


def test_custom_slots_setting(client):
    r = client.put("/publish/settings", json={"slots": ["19:00", "9:30"]})
    assert r.status_code == 200 and r.json()["slots"] == ["09:30", "19:00"]
    assert client.put("/publish/settings", json={"slots": ["24:00"]}).status_code == 422


# ---------------------------------------------------------------- YouTube

class FakeInsert:
    def __init__(self, calls):
        self.calls, self.step = calls, 0

    def next_chunk(self, num_retries=0):
        self.step += 1
        if self.step == 1:
            return SimpleNamespace(progress=lambda: 0.5), None
        return None, {"id": "yt123"}


class FakeService:
    def __init__(self):
        self.calls = []

    def videos(self):
        return SimpleNamespace(insert=self._insert)

    def _insert(self, part, body, media_body):
        self.calls.append(body)
        return FakeInsert(self.calls)

    def channels(self):
        return SimpleNamespace(list=lambda **kw: SimpleNamespace(execute=lambda: {
            "items": [{"id": "UC1", "snippet": {"title": "Meu Canal"}}]}))


@pytest.fixture()
def connected(client, monkeypatch):
    service = FakeService()
    monkeypatch.setattr(client.youtube, "_service", lambda owner: service)
    token = config.DATA_DIR / "youtube_token.json"
    token.write_text(json.dumps({"refresh_token": "r", "client_id": "c", "client_secret": "s",
                                 "token": "t"}))
    return service


def test_connect_url_and_callback(client, monkeypatch):
    url = client.get("/youtube/connect").json()["url"]
    assert "accounts.google.com" in url and "cid.apps.googleusercontent.com" in url
    assert "redirect_uri=https%3A%2F%2Feditor.example%2Fyoutube%2Fcallback" in url
    assert "access_type=offline" in url
    state = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))["state"]

    # callback com state errado: recusa sem tocar no Google
    assert "inválido" in client.get("/youtube/callback?state=xx&code=c").text

    creds = SimpleNamespace(refresh_token="r1", to_json=lambda: json.dumps(
        {"refresh_token": "r1", "token": "t", "client_id": "c", "client_secret": "s"}))
    flows = []

    class FakeFlow:
        code_verifier = None
        credentials = creds

        def fetch_token(self, code):
            flows.append((code, self.code_verifier))

    monkeypatch.setattr(client.youtube, "_flow", lambda state=None: FakeFlow())
    monkeypatch.setattr(client.youtube, "_service", lambda owner: FakeService())
    page = client.get(f"/youtube/callback?state={state}&code=abc").text
    assert "Meu Canal" in page and flows and flows[0][0] == "abc"
    st = client.get("/youtube/status").json()
    assert st["connected"] and st["channel"]["title"] == "Meu Canal" and not st["auto_upload"]
    # o mesmo state não serve duas vezes
    assert "inválido" in client.get(f"/youtube/callback?state={state}&code=abc").text


def test_manual_test_upload_without_audit_is_private_without_publish_at(client, connected):
    item = client.post("/publish/queue", json={"video_id": client.vid,
                                               "short_ids": [client.shorts[0]["id"]]}).json()[0]
    assert item["mode"] == "assisted"  # sem auditoria não sobe sozinho
    assert client.post(f"/publish/queue/{item['id']}/upload").status_code == 200
    done = wait_item(client, item["id"], {"uploaded", "failed"})
    assert done["status"] == "uploaded" and done["youtube_id"] == "yt123"
    body = connected.calls[0]
    assert body["status"]["privacyStatus"] == "private" and "publishAt" not in body["status"]
    assert body["snippet"]["title"] == item["title"]


def test_audited_schedule_uploads_now_with_publish_at(client, connected, monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_AUDITED", True)
    items = client.post("/publish/queue", json={"video_id": client.vid}).json()
    assert all(i["mode"] == "api" for i in items)
    for item in items:
        done = wait_item(client, item["id"], {"uploaded", "failed"})
        assert done["status"] == "uploaded" and done["scheduled_on_youtube"] is True
    published = sorted(b["status"]["publishAt"] for b in connected.calls)
    assert published == sorted(i["slot_at"] for i in items)
    # já enviado: não dá para remarcar pela fila (só no YouTube Studio)
    assert client.patch(f"/publish/queue/{items[0]['id']}",
                        json={"slot_at": "2030-01-01T15:00:00Z"}).status_code == 409


def test_upload_quota_error_is_readable(client, connected, monkeypatch):
    def boom(*a, **k):
        raise client.youtube.YouTubeError("limite diário de envios do YouTube atingido; tente amanhã")
    monkeypatch.setattr(client.youtube, "upload", boom)
    item = client.post("/publish/queue", json={"video_id": client.vid,
                                               "short_ids": [client.shorts[0]["id"]]}).json()[0]
    client.post(f"/publish/queue/{item['id']}/upload")
    failed = wait_item(client, item["id"], {"failed"})
    assert "limite diário" in failed["error"]


# ---------------------------------------------------------------- contas

def test_accounts_isolate_videos_queue_and_channel(client, connected):
    # o administrador (API_KEY) cria a conta da segunda pessoa
    created = client.post("/admin/users", json={"name": "Celular 2"})
    assert created.status_code == 201, created.text
    other = {"X-API-Key": created.json()["token"]}
    uid = created.json()["user"]["id"]
    assert "token_hash" not in created.json()["user"]
    assert client.get("/me", headers=other).json()["name"] == "Celular 2"
    assert client.post("/admin/users", json={"name": "celular 2"}).status_code == 409

    # vídeos: a conta nova não vê nem mexe nos vídeos da principal
    assert client.get("/videos", headers=other).json() == []
    assert client.get(f"/videos/{client.vid}", headers=other).status_code == 404
    sid = client.shorts[0]["id"]
    assert client.get(f"/videos/{client.vid}/shorts/{sid}/video",
                      headers=other).status_code == 404
    assert client.delete(f"/videos/{client.vid}", headers=other).status_code == 404
    assert client.post("/publish/queue", headers=other,
                       json={"video_id": client.vid}).status_code == 404

    # agenda: cada um vê só a sua; o mesmo horário pode ser usado pelos dois canais
    mine = client.post("/publish/queue", json={"video_id": client.vid,
                                               "short_ids": [sid]}).json()[0]
    assert client.get("/publish/queue", headers=other).json() == []
    assert client.patch(f"/publish/queue/{mine['id']}", headers=other,
                        json={"status": "posted"}).status_code == 404
    assert client.put("/publish/settings", headers=other,
                      json={"slots": ["09:00"]}).status_code == 200
    assert client.get("/publish/settings").json()["slots"] != ["09:00"]

    # canal: a principal está conectada, a conta nova não
    assert client.get("/youtube/status").json()["connected"] is True
    assert client.get("/youtube/status", headers=other).json()["connected"] is False

    # só o administrador gerencia contas
    assert client.get("/admin/users", headers=other).status_code == 403
    assert [u["id"] for u in client.get("/admin/users").json()] == [uid]

    # nova chave invalida a antiga; apagar a conta tira o acesso
    new_token = client.post(f"/admin/users/{uid}/token").json()["token"]
    assert client.get("/videos", headers=other).status_code == 401
    assert client.get("/videos", headers={"X-API-Key": new_token}).status_code == 200
    assert client.delete(f"/admin/users/{uid}?purge=true").status_code == 204
    assert client.get("/videos", headers={"X-API-Key": new_token}).status_code == 401
    assert client.get("/publish/queue").json()[0]["id"] == mine["id"]


def test_each_account_connects_its_own_channel(client, monkeypatch):
    token = client.post("/admin/users", json={"name": "Desktop"}).json()["token"]
    other = {"X-API-Key": token}
    url = client.get("/youtube/connect", headers=other).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    class Creds:
        refresh_token = "r"

        def to_json(self):
            return json.dumps({"refresh_token": "r", "client_id": "c", "client_secret": "s",
                               "token": "t"})

    class FakeFlow:
        credentials = Creds()
        code_verifier = None

        def fetch_token(self, code):
            pass

    monkeypatch.setattr(client.youtube, "_flow", lambda state=None: FakeFlow())
    monkeypatch.setattr(client.youtube, "_service", lambda owner: FakeService())
    assert "conectado" in client.get(f"/youtube/callback?state={state}&code=abc").text
    assert client.get("/youtube/status", headers=other).json()["connected"] is True
    assert client.get("/youtube/status").json()["connected"] is False
