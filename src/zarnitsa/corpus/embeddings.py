"""Embedding client — BGE-M3 via the Hugging Face Inference API.

Corpus chunks are embedded once, offline (see index.build_index) and the
vectors are committed with the snapshot. At request time only the short query
is embedded live. Query and corpus MUST use the same model, so both go through
this client.
"""

from __future__ import annotations

import time

import certifi
import httpx
import numpy as np

from zarnitsa.config import settings

# HF deprecated api-inference.huggingface.co; use the Inference Providers router.
_ENDPOINT = "https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"
_DIM = 1024  # BGE-M3 dense dimension


class EmbeddingError(RuntimeError):
    """Raised when the embedding backend is misconfigured or unavailable."""


def _client() -> httpx.Client:
    if not settings.hf_token:
        raise EmbeddingError(
            "HF_TOKEN is not set — export it locally and add it to the Render env."
        )
    return httpx.Client(
        headers={"Authorization": f"Bearer {settings.hf_token}"},
        timeout=120.0,
        verify=certifi.where(),
    )


def _pool(data: object) -> np.ndarray:
    """Normalize the HF response into a 2-D (n, dim) float array.

    Sentence-transformers models return pooled sentence vectors; if a model
    returns token-level embeddings (3-D) we mean-pool them.
    """
    arr = np.asarray(data, dtype=np.float32)
    if arr.ndim == 3:      # (n, tokens, dim) -> mean-pool over tokens
        arr = arr.mean(axis=1)
    elif arr.ndim == 1:    # single vector -> (1, dim)
        arr = arr[None, :]
    return arr


def embed_texts(texts: list[str], *, batch_size: int = 16, max_retries: int = 4) -> np.ndarray:
    """Embed a list of texts, unit-normalized for cosine similarity."""
    if not texts:
        return np.zeros((0, _DIM), dtype=np.float32)
    url = _ENDPOINT.format(model=settings.embedding_model)
    out: list[np.ndarray] = []
    with _client() as client:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            payload = {"inputs": batch}
            resp: httpx.Response | None = None
            for attempt in range(max_retries):
                resp = client.post(url, json=payload)
                if resp.status_code == 503:      # model still loading
                    time.sleep(5 * (attempt + 1))
                    continue
                if resp.status_code == 429:      # rate limited
                    time.sleep(10 * (attempt + 1))
                    continue
                if resp.status_code == 404:
                    raise EmbeddingError(
                        f"model '{settings.embedding_model}' not served by HF serverless "
                        f"inference; use an HF Inference Endpoint or another provider."
                    )
                resp.raise_for_status()
                break
            else:
                code = resp.status_code if resp is not None else "?"
                body = resp.text[:200] if resp is not None else ""
                raise EmbeddingError(f"HF inference failed after retries: {code} {body}")
            out.append(_pool(resp.json()))
    vecs = np.vstack(out).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    return vecs


def embed_query(text: str) -> np.ndarray:
    """Embed a single query string -> (dim,) unit vector."""
    return embed_texts([text])[0]
