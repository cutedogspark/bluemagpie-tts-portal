import subprocess
import tempfile

import numpy as np
import soundfile as sf


def decode_to_wav(src_bytes: bytes, out_wav_path: str) -> str:
    """任意瀏覽器音訊（webm/ogg/wav…）→ 48kHz 單聲道 16-bit PCM wav。"""
    with tempfile.NamedTemporaryFile(suffix=".bin") as src:
        src.write(src_bytes)
        src.flush()
        subprocess.run(
            ["ffmpeg", "-y", "-i", src.name,
             "-ar", "48000", "-ac", "1", "-sample_fmt", "s16", out_wav_path],
            check=True, capture_output=True,
        )
    return out_wav_path


def samples_to_mp3(samples: np.ndarray, sample_rate: int) -> bytes:
    """float32 mono → mp3 bytes（先寫 wav 再用 ffmpeg 轉 mp3）。"""
    with tempfile.NamedTemporaryFile(suffix=".wav") as wavf, \
         tempfile.NamedTemporaryFile(suffix=".mp3") as mp3f:
        sf.write(wavf.name, samples, sample_rate, subtype="PCM_16")
        subprocess.run(
            ["ffmpeg", "-y", "-i", wavf.name, "-codec:a", "libmp3lame",
             "-qscale:a", "2", mp3f.name],
            check=True, capture_output=True,
        )
        with open(mp3f.name, "rb") as f:
            return f.read()
