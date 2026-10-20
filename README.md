# ABEL

A personal, distributed cognitive system that runs entirely on its owner's devices.

ABEL has a central core on the main PC and lightweight nodes on each authorized device. Nodes observe (system state, active window, presence) and report to the core over an authenticated, encrypted channel. The core stores events and facts, builds a memory of its user, and talks through a local web interface. No cloud, no third-party data: everything stays on hardware the user owns.

> Personal project in active development. Code comments and internal docs are in Spanish.

## Architecture

- **Core** (`nucleo/`): asyncio services — internal event bus, scheduler, memory, reasoning, language and web UI.
- **Nodes** (`nodos/`): sensors plus a persistent SQLite queue, so nothing is lost while the core is offline. Exponential backoff on reconnect.
- **Protocol** (`protocolos/`): WebSockets over TLS with certificate pinning, device authentication by signed challenge, ACKs and idempotency.
- **Memory**: PostgreSQL for events and assertions (with attribution, corrections, negations and expiry); Qdrant for similarity search.
- **Language**: intent recognition by embedding similarity. A local LLM is loaded on demand and released when idle to free VRAM — it is one organ, not the brain. Exact calculations are answered directly, without the model.

## Highlights

- 38 architecture decision records in `docs/decisiones/`
- Hand-written SQL (no ORM), least-privilege database user, versioned schema migrations
- Test suite in `tests/`
- Runs in the background from the Windows system tray

## Stack

Python (asyncio) · PostgreSQL · Qdrant · sentence-transformers · PyTorch · WebSockets · TLS · SQLite · Docker Compose · JavaScript · Three.js · HTML/CSS

## Running locally

1. Copy `.env.example` to `.env` and fill in the values.
2. `docker compose up -d` (PostgreSQL + Qdrant, bound to localhost only).
3. Create a virtual environment and `pip install -r requirements.txt`.
4. Apply the files in `db/schema/` in order.
5. Generate the TLS certificate (`python -m scripts.certificado`) and authorize a device (`python -m scripts.dispositivos autorizar ...`).
6. `python abel.py`

## Status

Version 0.0.1. Phase 6 (similarity-based recognition) closed in August 2026; V.1 rebuild in progress. See `docs/fases/`.

## History

ABEL succeeds V.0.2, an earlier purely emergent experiment with no external dependencies. That version is kept as a historical archive; its design and philosophical lessons shaped this iteration. Design principles are in `docs/filosofia/`.
