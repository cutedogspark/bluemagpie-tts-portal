import os
import subprocess
import tempfile
import threading

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator

from .audio import decode_to_wav, samples_to_mp3
from .deps import get_model_service
from .model_service import ModelService

app = FastAPI(title="BlueMagpie TTS Service")

_GEN_LOCK = threading.Lock()


def _locked(fn, *args):
    with _GEN_LOCK:
        return fn(*args)


class TTSRequest(BaseModel):
    text: str
    cfg_value: float = Field(default=2.0, ge=1.0, le=4.0)
    inference_timesteps: int = Field(default=10, ge=4, le=30)
    speaker: str | None = None

    @field_validator("text")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("text must not be empty")
        if len(stripped) > 1000:
            raise ValueError("text must not exceed 1000 characters")
        return stripped


@app.get("/healthz")
def healthz(svc: ModelService = Depends(get_model_service)):
    return {"ready": bool(getattr(svc, "ready", False))}


@app.get("/api/speakers")
def speakers(svc: ModelService = Depends(get_model_service)):
    return {"speakers": svc.list_speakers()}


_GPU_FIELDS = "utilization.gpu,utilization.memory,power.draw,temperature.gpu,clocks.sm"


def _num(x: str):
    try:
        return float(x)
    except ValueError:
        return None  # "[N/A]" on GB10


def _gpu_memory_mb() -> dict:
    """Per-process GPU memory (MiB). GB10 has no global memory.used (unified
    memory), but per-compute-app memory IS queryable. We report this service's
    own usage (matched by pid) plus the total across all GPU processes."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory",
             "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=4,
        )
        mypid = str(os.getpid())
        self_mb, total_mb = None, 0.0
        for line in r.stdout.strip().splitlines():
            parts = [c.strip() for c in line.split(",")]
            if len(parts) >= 2:
                mb = _num(parts[1])
                if mb is None:
                    continue
                total_mb += mb
                if parts[0] == mypid:
                    self_mb = mb
        return {"mem_self_mb": self_mb, "mem_total_mb": total_mb or None}
    except (subprocess.SubprocessError, OSError):
        return {"mem_self_mb": None, "mem_total_mb": None}


def _torch_memory_mb() -> dict:
    """PyTorch's own view: 'active' memory moves with computation (rises during
    generation, falls after), unlike nvidia-smi's flat reserved-pool figure."""
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "mem_active_mb": round(torch.cuda.memory_allocated() / 1e6, 1),
                "mem_reserved_mb": round(torch.cuda.memory_reserved() / 1e6, 1),
            }
    except Exception:
        pass
    return {}


def _read_gpu() -> dict:
    """Live GB10 GPU stats via nvidia-smi. Global memory bytes are N/A on GB10
    (unified memory), so memory is reported per-process (see _gpu_memory_mb)."""
    try:
        r = subprocess.run(
            ["nvidia-smi", f"--query-gpu={_GPU_FIELDS}",
             "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=4,
        )
        p = [c.strip() for c in r.stdout.strip().split(",")]
        out = {
            "available": True,
            "util": _num(p[0]), "mem_util": _num(p[1]),
            "power": _num(p[2]), "temp": _num(p[3]), "clock": _num(p[4]),
        }
        out.update(_gpu_memory_mb())
        out.update(_torch_memory_mb())
        return out
    except (subprocess.SubprocessError, OSError, IndexError):
        return {"available": False}


@app.get("/api/gpu")
async def gpu():
    return await run_in_threadpool(_read_gpu)


@app.post("/api/tts")
async def tts(req: TTSRequest, svc: ModelService = Depends(get_model_service)):
    try:
        samples = await run_in_threadpool(
            _locked, svc.synthesize, req.text, req.cfg_value, req.speaker, req.inference_timesteps
        )
    except KeyError:
        raise HTTPException(status_code=400, detail=f"unknown speaker: {req.speaker}")
    mp3 = await run_in_threadpool(samples_to_mp3, samples, svc.sample_rate)
    return Response(content=mp3, media_type="audio/mpeg")


_CLONE_MODES = ("centroid", "reference", "prompt")


@app.post("/api/clone")
async def clone(
    consent: str = Form(...),
    text: str = Form(...),
    cfg_value: float = Form(2.8),
    inference_timesteps: int = Form(10),
    mode: str = Form("prompt"),
    prompt_text: str = Form(""),
    audio: UploadFile = File(...),
    svc: ModelService = Depends(get_model_service),
):
    if consent.lower() not in ("true", "1", "on", "yes"):
        raise HTTPException(status_code=422, detail="consent required")
    stripped = text.strip()
    if not stripped:
        raise HTTPException(status_code=422, detail="text must not be empty")
    if len(stripped) > 1000:
        raise HTTPException(status_code=422, detail="text must not exceed 1000 characters")
    text = stripped
    if not (1.0 <= cfg_value <= 4.0):
        raise HTTPException(status_code=422, detail="cfg_value out of range")
    if not (4 <= inference_timesteps <= 30):
        raise HTTPException(status_code=422, detail="inference_timesteps out of range")
    if mode not in _CLONE_MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {_CLONE_MODES}")
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=422, detail="empty audio")
    # prompt mode needs the reference transcript; without it, fall back to the
    # original centroid mode (reference mode is unstable on this checkpoint).
    pt = prompt_text.strip()
    if mode == "prompt" and not pt:
        mode = "centroid"
    with tempfile.TemporaryDirectory() as d:
        try:
            wav = decode_to_wav(raw, os.path.join(d, "ref.wav"))
        except subprocess.CalledProcessError:
            raise HTTPException(status_code=422, detail="could not decode audio")
        if mode == "reference":
            samples = await run_in_threadpool(
                _locked, svc.synthesize_with_reference, text, wav, cfg_value, inference_timesteps
            )
        elif mode == "prompt":
            samples = await run_in_threadpool(
                _locked, svc.synthesize_with_prompt, text, wav, pt, cfg_value, inference_timesteps
            )
        else:  # centroid (original)
            centroid = await run_in_threadpool(svc.extract_centroid, wav)
            samples = await run_in_threadpool(
                _locked, svc.synthesize_with_centroid, text, centroid, cfg_value, inference_timesteps
            )
    mp3 = await run_in_threadpool(samples_to_mp3, samples, svc.sample_rate)
    return Response(content=mp3, media_type="audio/mpeg")
