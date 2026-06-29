import os
import asyncio  # noqa: F401  (保留給未來)
from typing import Protocol
import numpy as np


class ModelService(Protocol):
    sample_rate: int
    ready: bool

    def list_speakers(self) -> list[str]: ...
    def synthesize(self, text: str, cfg_value: float, speaker: str | None = None, inference_timesteps: int = 10) -> np.ndarray: ...
    def synthesize_with_centroid(self, text: str, centroid: np.ndarray, cfg_value: float, inference_timesteps: int = 10) -> np.ndarray: ...
    def synthesize_with_reference(self, text: str, wav_path: str, cfg_value: float, inference_timesteps: int = 10) -> np.ndarray: ...
    def synthesize_with_prompt(self, text: str, wav_path: str, prompt_text: str, cfg_value: float, inference_timesteps: int = 10) -> np.ndarray: ...
    def extract_centroid(self, wav_path: str) -> np.ndarray: ...


def _to_numpy(audio) -> np.ndarray:
    if isinstance(audio, np.ndarray):
        arr = audio
    else:  # torch.Tensor
        arr = audio.detach().to("cpu").float().numpy()
    return np.asarray(arr, dtype="float32").reshape(-1)


class BlueMagpieModelService:
    sample_rate = 48000

    def __init__(self, model, presets: dict):
        self._model = model
        self._presets = presets  # name -> centroid(np.ndarray[192])
        self.ready = True

    def list_speakers(self) -> list[str]:
        return list(self._presets.keys())

    def synthesize(self, text: str, cfg_value: float, speaker: str | None = None,
                   inference_timesteps: int = 10) -> np.ndarray:
        kwargs = {}
        if speaker is not None:
            if speaker not in self._presets:
                raise KeyError(speaker)
            kwargs["speaker_centroid"] = self._presets[speaker]
        audio = self._model.generate(
            target_text=text, cfg_value=cfg_value, inference_timesteps=inference_timesteps, **kwargs
        )
        return _to_numpy(audio)

    def synthesize_with_centroid(self, text: str, centroid, cfg_value: float,
                                 inference_timesteps: int = 10) -> np.ndarray:
        audio = self._model.generate(
            target_text=text, speaker_centroid=centroid, cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
        )
        return _to_numpy(audio)

    def synthesize_with_reference(self, text: str, wav_path: str, cfg_value: float,
                                  inference_timesteps: int = 10) -> np.ndarray:
        audio = self._model.generate(
            target_text=text, reference_wav_path=wav_path, cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
        )
        return _to_numpy(audio)

    def synthesize_with_prompt(self, text: str, wav_path: str, prompt_text: str, cfg_value: float,
                               inference_timesteps: int = 10) -> np.ndarray:
        audio = self._model.generate(
            target_text=text, prompt_wav_path=wav_path, prompt_text=prompt_text, cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
        )
        return _to_numpy(audio)

    def extract_centroid(self, wav_path: str):
        from bluemagpie import extract_speaker_centroid
        return extract_speaker_centroid(wav_path)


def build_model_service() -> ModelService:
    import os
    import torch
    from huggingface_hub import snapshot_download
    from transformers import PreTrainedTokenizerFast
    from bluemagpie import BlueMagpieModel

    token = os.environ.get("HF_TOKEN") or True
    device = os.environ.get("BLUEMAGPIE_DEVICE", "cuda")
    # Offline path: if BLUEMAGPIE_MODEL_DIR points at a local snapshot folder
    # (e.g. copied in via USB), load from it directly and skip any HF download.
    local_dir = os.environ.get("BLUEMAGPIE_MODEL_DIR")
    if local_dir and os.path.isdir(local_dir):
        model_dir = local_dir
    else:
        model_dir = snapshot_download("OpenFormosa/BlueMagpie-TTS", token=token)
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_file=os.path.join(model_dir, "tokenizer.json")
    )
    model = BlueMagpieModel.from_local(
        model_dir, tokenizer=tokenizer, training=False, device=device
    )
    presets_path = os.path.join(model_dir, "checkpoints", "speaker_centroids.pt")
    presets = {}
    if os.path.exists(presets_path):
        raw = torch.load(presets_path, weights_only=True)
        # Shipped format: {"speaker_ids": [name, ...],
        #                  "centroids": Tensor[N, 192], "dim": int}
        # Keep each centroid as a torch tensor — generate() moves it to the
        # model device/dtype itself.
        if isinstance(raw, dict) and "speaker_ids" in raw and "centroids" in raw:
            cents = raw["centroids"]
            presets = {name: cents[i] for i, name in enumerate(raw["speaker_ids"])}
        elif isinstance(raw, dict):
            presets = {k: v for k, v in raw.items() if torch.is_tensor(v)}
    return BlueMagpieModelService(model, presets)
