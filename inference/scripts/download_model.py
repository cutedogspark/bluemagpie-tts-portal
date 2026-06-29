#!/usr/bin/env python3
"""Download the BlueMagpie-TTS model on a machine with fast internet, into a
plain local folder you can copy to the GB10 via USB.

Usage (on the OTHER computer, not the GB10):

    pip install "huggingface_hub>=0.24"
    export HF_TOKEN=hf_xxx              # your Hugging Face token
    python download_model.py            # -> ./BlueMagpie-TTS  (~7.75 GB)
    # or choose an output dir:
    python download_model.py /path/to/usb/BlueMagpie-TTS

Then on the GB10, point the service at the copied folder:

    export BLUEMAGPIE_MODEL_DIR=/path/to/BlueMagpie-TTS

The download is resumable — re-run it if interrupted.
"""
import os
import sys

from huggingface_hub import snapshot_download

REPO = "OpenFormosa/BlueMagpie-TTS"


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "./BlueMagpie-TTS"
    token = os.environ.get("HF_TOKEN") or True  # True = use cached login
    print(f"Downloading {REPO} -> {out}")
    path = snapshot_download(
        REPO,
        token=token,
        local_dir=out,
        # keep real files (no symlinks) so the folder is self-contained for USB
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print("Done. Model folder:", path)
    print("Copy this whole folder to the GB10, then set BLUEMAGPIE_MODEL_DIR to it.")


if __name__ == "__main__":
    main()
