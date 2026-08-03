"""Smoke test: confirm BGE-M3 responds via the HF Inference router.

Run from the project root in your own terminal (it reads HF_TOKEN from .env):
    python scripts/smoke_embed.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from zarnitsa.config import settings  # noqa: E402
from zarnitsa.corpus.embeddings import EmbeddingError, embed_query  # noqa: E402

print("HF token present:", bool(settings.hf_token))
print("embedding model :", settings.embedding_model)
try:
    vec = embed_query("nuclear deterrence test sentence")
    norm = float((vec * vec).sum() ** 0.5)
    print("OK  - vector shape:", vec.shape, "| unit norm:", round(norm, 4))
    print("BGE-M3 is reachable. You can build the index now.")
except EmbeddingError as e:
    print("EMBEDDING ERROR:", e)
except Exception as e:  # noqa: BLE001
    print("ERROR:", type(e).__name__, "::", str(e)[:300])
