import threading

from .model_service import ModelService, build_model_service

_service: ModelService | None = None
_build_lock = threading.Lock()


def get_model_service() -> ModelService:
    global _service
    if _service is None:
        with _build_lock:
            if _service is None:
                _service = build_model_service()
    return _service
