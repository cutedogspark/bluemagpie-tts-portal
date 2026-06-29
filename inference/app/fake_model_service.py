import numpy as np


class FakeModelService:
    """測試用：回固定 440Hz 正弦波，不需 GPU/模型。"""

    sample_rate = 48000
    ready = True

    def _tone(self, seconds: float = 0.1) -> np.ndarray:
        n = int(self.sample_rate * seconds)
        t = np.arange(n) / self.sample_rate
        return (0.2 * np.sin(2 * np.pi * 440 * t)).astype("float32")

    def list_speakers(self) -> list[str]:
        return ["hung_yi_lee", "female_voice"]

    def synthesize(self, text: str, cfg_value: float, speaker: str | None = None,
                   inference_timesteps: int = 10) -> np.ndarray:
        if speaker is not None and speaker not in self.list_speakers():
            raise KeyError(speaker)
        return self._tone()

    def synthesize_with_centroid(self, text: str, centroid: np.ndarray, cfg_value: float,
                                 inference_timesteps: int = 10) -> np.ndarray:
        return self._tone()

    def synthesize_with_reference(self, text: str, wav_path: str, cfg_value: float,
                                  inference_timesteps: int = 10) -> np.ndarray:
        return self._tone()

    def synthesize_with_prompt(self, text: str, wav_path: str, prompt_text: str, cfg_value: float,
                               inference_timesteps: int = 10) -> np.ndarray:
        return self._tone()

    def extract_centroid(self, wav_path: str) -> np.ndarray:
        return np.zeros(192, dtype="float32")
