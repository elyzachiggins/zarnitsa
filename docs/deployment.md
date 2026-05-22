# Deployment

## Modes

| Mode | Backbone | Hardware | Council size | Notes |
|---|---|---|---|---|
| **Cloud** | Anthropic Claude | API key only | Full 8 + 2 | Default; best fidelity |
| **Offline-standard** | Ollama / Gemma 3 27B | RTX 4080-class GPU (16GB+ VRAM) | Full 8 + 2 | Sweet spot; Apache 2.0 |
| **Offline-heavy** | Ollama / Qwen 2.5 72B | RTX 4090 / A100 | Full 8 + 2 | Best Russian fidelity; slower |
| **Offline-light** | Ollama / Gemma 3 4B (or E4B equivalent) | 8GB RAM laptop | Reduced (3 personas + synthesizer) | Edge-resident; degraded |

Set the backbone with `ZARNITSA_BACKBONE` in `.env`.

## Air-gapped install

1. On a connected machine, build the Docker image and export it:
   ```bash
   docker build -t zarnitsa:latest -f docker/Dockerfile .
   docker save zarnitsa:latest | gzip > zarnitsa.tar.gz
   ```
2. Pull the local model on a connected machine and export the Ollama volume:
   ```bash
   ollama pull gemma3:27b
   tar -czf ollama-models.tar.gz -C ~/.ollama .
   ```
3. Snapshot the corpus (`data/corpus/snapshots/<date>/`) and bundle with the image and model files.
4. On the air-gapped host:
   ```bash
   docker load < zarnitsa.tar.gz
   # Restore ollama models to its data volume
   docker compose -f docker/offline.yml up
   ```

## Gating the deployed API

The MIT license covers the code. Deployments serving the council API to external users should gate access — license check, mil-domain email verification, or other vetting. This prevents the system from being used as a "Russian-state-narrative chatbot" by anonymous users while keeping the code itself open for inspection and contribution.

Gate implementation (TODO) lives in `src/zarnitsa/api/auth.py`.
