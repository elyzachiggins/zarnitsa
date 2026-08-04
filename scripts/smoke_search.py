"""Smoke test: run a live retrieval against the built index.

Shows the hybrid search + persona boost pulling real chunks for a scenario.
Run from the project root in your own terminal (needs HF_TOKEN in .env):
    python scripts/smoke_search.py
    python scripts/smoke_search.py "your own scenario text"
"""

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from zarnitsa.corpus.index import ChunkIndex  # noqa: E402

query = sys.argv[1] if len(sys.argv) > 1 else (
    "Условия применения ядерного оружия при нападении неядерного государства "
    "при поддержке ядерной державы"
)

idx = ChunkIndex.load()
print(f"index: {len(idx.chunks)} chunks\nquery: {query}\n")
print("top chunks (CINC persona boost):")
for chunk, score in idx.search(query, top_k=6, persona="commander_in_chief"):
    preview = " ".join(chunk.text.split())[:110]
    print(f"  {score:.3f}  [{chunk.tier.value}]  {chunk.entry_id} — {chunk.anchor}")
    print(f"         {preview}")
