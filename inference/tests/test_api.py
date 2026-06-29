import subprocess

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.deps import get_model_service
from app.fake_model_service import FakeModelService


def _fake_recording(tmp_path):
    p = tmp_path / "rec.ogg"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=1",
         "-ar", "24000", "-ac", "1", str(p)],
        check=True, capture_output=True,
    )
    return p.read_bytes()


@pytest.fixture
def client():
    app.dependency_overrides[get_model_service] = lambda: FakeModelService()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ready"] is True


def test_speakers(client):
    r = client.get("/api/speakers")
    assert r.status_code == 200
    assert r.json()["speakers"] == ["hung_yi_lee", "female_voice"]


def test_tts_returns_mp3(client):
    r = client.post("/api/tts", json={"text": "今天天氣真好", "cfg_value": 2.0})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    body = r.content
    assert body[:3] == b"ID3" or (body[0] == 0xFF and (body[1] & 0xE0) == 0xE0)


def test_tts_rejects_empty_text(client):
    r = client.post("/api/tts", json={"text": "  "})
    assert r.status_code == 422


def test_tts_rejects_long_text(client):
    r = client.post("/api/tts", json={"text": "我" * 1001, "cfg_value": 2.0})
    assert r.status_code == 422


def test_tts_rejects_cfg_value_too_high(client):
    r = client.post("/api/tts", json={"text": "hello", "cfg_value": 9.9})
    assert r.status_code == 422


def test_tts_rejects_cfg_value_negative(client):
    r = client.post("/api/tts", json={"text": "hello", "cfg_value": -1})
    assert r.status_code == 422


def test_clone_returns_mp3(client, tmp_path):
    rec = _fake_recording(tmp_path)
    r = client.post(
        "/api/clone",
        data={"text": "你好，這是我的聲音", "cfg_value": "2.8", "consent": "true"},
        files={"audio": ("rec.ogg", rec, "audio/ogg")},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert len(r.content) > 200


def test_clone_requires_consent(client, tmp_path):
    rec = _fake_recording(tmp_path)
    r = client.post(
        "/api/clone",
        data={"text": "你好", "cfg_value": "2.8"},
        files={"audio": ("rec.ogg", rec, "audio/ogg")},
    )
    assert r.status_code == 422


def test_clone_reference_mode(client, tmp_path):
    rec = _fake_recording(tmp_path)
    r = client.post(
        "/api/clone",
        data={"text": "參考音模式", "cfg_value": "2.8", "consent": "true", "mode": "reference"},
        files={"audio": ("rec.ogg", rec, "audio/ogg")},
    )
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"


def test_clone_prompt_mode(client, tmp_path):
    rec = _fake_recording(tmp_path)
    r = client.post(
        "/api/clone",
        data={
            "text": "語音接續模式", "cfg_value": "2.8", "consent": "true",
            "mode": "prompt", "prompt_text": "這是我念的腳本",
        },
        files={"audio": ("rec.ogg", rec, "audio/ogg")},
    )
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"


def test_clone_unknown_mode_rejected(client, tmp_path):
    rec = _fake_recording(tmp_path)
    r = client.post(
        "/api/clone",
        data={"text": "x", "cfg_value": "2.8", "consent": "true", "mode": "bogus"},
        files={"audio": ("rec.ogg", rec, "audio/ogg")},
    )
    assert r.status_code == 422


def test_gpu_endpoint_shape(client):
    r = client.get("/api/gpu")
    assert r.status_code == 200
    body = r.json()
    assert "available" in body
    # nvidia-smi absent in test env -> graceful unavailable; on GB10 -> fields present
    if body["available"]:
        assert set(["util", "power", "temp", "clock"]).issubset(body)


def test_tts_inference_timesteps_ok(client):
    r = client.post("/api/tts", json={"text": "步數測試", "cfg_value": 2.0, "inference_timesteps": 8})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"


def test_tts_inference_timesteps_out_of_range(client):
    r = client.post("/api/tts", json={"text": "x", "inference_timesteps": 999})
    assert r.status_code == 422


def test_clone_inference_timesteps_out_of_range(client, tmp_path):
    rec = _fake_recording(tmp_path)
    r = client.post(
        "/api/clone",
        data={"text": "x", "consent": "true", "mode": "centroid", "inference_timesteps": "1"},
        files={"audio": ("rec.ogg", rec, "audio/ogg")},
    )
    assert r.status_code == 422
