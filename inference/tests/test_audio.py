import subprocess
import wave
from pathlib import Path

import numpy as np
import soundfile as sf

from app.audio import decode_to_wav, samples_to_mp3


def _make_source_ogg(tmp_path: Path) -> bytes:
    # 用 ffmpeg 產生 1 秒 mono 24k ogg 當「上傳音訊」
    src = tmp_path / "src.ogg"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-ar", "24000", "-ac", "1", str(src)],
        check=True, capture_output=True,
    )
    return src.read_bytes()


def test_decode_to_wav_48k_mono(tmp_path):
    src_bytes = _make_source_ogg(tmp_path)
    out = decode_to_wav(src_bytes, str(tmp_path / "out.wav"))
    with wave.open(out, "rb") as w:
        assert w.getframerate() == 48000
        assert w.getnchannels() == 1
    data, sr = sf.read(out)
    assert sr == 48000 and len(data) > 0


def test_samples_to_mp3_returns_valid_mp3(tmp_path):
    sr = 48000
    t = np.arange(sr) / sr
    samples = (0.2 * np.sin(2 * np.pi * 440 * t)).astype("float32")
    data = samples_to_mp3(samples, sr)
    assert isinstance(data, bytes) and len(data) > 200
    # mp3：ID3 標頭或 frame sync 0xFFE
    assert data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)
