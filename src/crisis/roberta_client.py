"""
RoBERTa suicide-prediction client.

Returns the suicide-class probability for a single message.

Mode resolution:
  - If `ROBERTA_REMOTE_URL` env var is set -> POST to `{URL}/classify`.
  - Otherwise load `Models/roberta-base-suicide-prediction-phr` locally on
    first call and reuse it (CPU is ~56ms/msg, validated acceptable).

Failures return 0.0 so the rest of the crisis pipeline (keyword + LLM) still
runs. This is the stage-1.5 signal — never the sole gate.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "Models" / "roberta-base-suicide-prediction-phr"
_HF_FALLBACK_ID = "vibhorag101/roberta-base-suicide-prediction-phr"

_model_lock = threading.Lock()
_local: Optional[Tuple[object, object, str]] = None  # (tokenizer, model, device)
_local_load_failed = False


def _load_local():
    global _local, _local_load_failed
    if _local is not None or _local_load_failed:
        return _local
    with _model_lock:
        if _local is not None or _local_load_failed:
            return _local
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            source = str(_MODEL_DIR) if _MODEL_DIR.exists() else _HF_FALLBACK_ID
            t0 = time.perf_counter()
            tok = AutoTokenizer.from_pretrained(source)
            model = AutoModelForSequenceClassification.from_pretrained(source)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(device).eval()
            _local = (tok, model, device)
            logger.info(
                f"RoBERTa loaded from {source} on {device} "
                f"in {time.perf_counter() - t0:.1f}s"
            )
        except Exception as exc:
            _local_load_failed = True
            logger.warning(f"RoBERTa local load failed: {exc}")
            _local = None
    return _local


def _score_local(text: str) -> float:
    loaded = _load_local()
    if not loaded:
        return 0.0
    tok, model, device = loaded
    try:
        import torch

        with torch.inference_mode():
            enc = tok(
                [text],
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            ).to(device)
            probs = torch.softmax(model(**enc).logits, dim=-1)[:, 0]  # idx 0 = suicide
            return float(probs[0].cpu().item())
    except Exception as exc:
        logger.warning(f"RoBERTa local score failed: {exc}")
        return 0.0


def _score_remote(text: str, url: str, timeout: float) -> float:
    import httpx

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(f"{url}/classify", json={"texts": [text]})
            r.raise_for_status()
            data = r.json()
            scores = data.get("scores") or []
            return float(scores[0]) if scores else 0.0
    except Exception as exc:
        logger.warning(f"RoBERTa remote score failed: {exc}")
        return 0.0


def score(text: str, *, timeout: float = 1.5) -> float:
    """Return suicide-class probability in [0, 1]. Never raises."""
    text = (text or "").strip()
    if not text:
        return 0.0

    remote_url = os.getenv("ROBERTA_REMOTE_URL", "").strip().rstrip("/")
    if remote_url:
        return _score_remote(text, remote_url, timeout)
    return _score_local(text)


def is_available() -> bool:
    """True if either the remote URL is set or local model files exist."""
    if os.getenv("ROBERTA_REMOTE_URL", "").strip():
        return True
    return _MODEL_DIR.exists()
