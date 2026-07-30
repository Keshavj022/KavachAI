# Kavach AI — Backend

> FastAPI backend powering the Kavach AI digital-arrest and fraud-shield platform.
> Handles real-time scam detection, the AI Decoy conversation engine, fraud-network
> intelligence, encrypted evidence, and all REST + WebSocket APIs.

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [WebSocket Channels](#websocket-channels)
- [Services](#services)
- [Database Models](#database-models)
- [Authentication & RBAC](#authentication--rbac)
- [Environment Variables](#environment-variables)
- [Setup](#setup)
- [Running](#running)
- [Docker](#docker)
- [Seeding Demo Data](#seeding-demo-data)
- [Graceful Degradation](#graceful-degradation)

---

## Architecture

The backend is a single **FastAPI** application serving three logical layers:

```
┌─────────────────────────────────────────────────────────────┐
│  API Layer (REST + WebSocket)                               │
│  auth · detection · call (ws) · decoy (ws) · reports ·      │
│  graph · evidence · contacts · guide                        │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│  Detection / Classification Layer (the brain)               │
│  Whisper STT → identifier extraction → known-scammer lookup │
│  → trained classifier → stateful ARC scorer → deterministic │
│  interrupt rule → LLM reasoning + RAG grounding             │
│  AI Decoy loop: LLM fraudster ⇄ LLM decoy, both voiced     │
│  live (Parler-TTS / Svara-TTS)                              │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│  Intelligence / Memory Layer                                │
│  Fraud-network graph (networkx) · Reports store · Encrypted │
│  evidence (Fernet/AES) · SQLite via SQLAlchemy 2.x          │
└─────────────────────────────────────────────────────────────┘
```

**Data spine:** A shared **identifier-extraction** step (phone / UPI / account / IFSC / URL)
is the seam both the detector and the graph depend on. One `Verdict` object is enriched as
it flows through the layers.

---

## Tech Stack

| Category | Technologies |
| --- | --- |
| **Framework** | Python 3.11+, FastAPI 0.115, Uvicorn (ASGI) |
| **Data / ORM** | SQLAlchemy 2.0 + SQLite (designed for Postgres swap), Pydantic v2 |
| **Auth / Security** | PyJWT (HS256), passlib/bcrypt, RBAC (citizen/authority), slowapi rate limiting, CORS |
| **Speech-to-Text** | faster-whisper (local, streaming) |
| **Detection ML** | scikit-learn (TF-IDF + LogReg classifier, arc tracker, SMS SVM) |
| **LLM (decoy)** | Groq (`llama-3.3-70b-versatile`) primary · Ollama (`gemma3:4b`) local fallback |
| **Text-to-Speech** | AI4Bharat Indic Parler-TTS (bf16, live) · Svara-TTS (vLLM/GPU) |
| **RAG / Embeddings** | sentence-transformers + ChromaDB |
| **Graph** | networkx (in-memory, from DB identifiers) |
| **Crypto** | cryptography (Fernet/AES) + hashlib (SHA-256) |
| **Alerts** | Twilio (simulated fallback) |
| **HTTP Client** | httpx |

---

## Project Structure

```
backend/
├── Dockerfile                   # Container image (python:3.11-slim)
├── requirements.txt             # All dependencies (pinned)
├── kavach.db                    # SQLite database (auto-created)
├── rag_corpus/                  # Markdown advisories for RAG grounding
│   ├── digital_arrest.md
│   ├── investment_fraud.md
│   ├── isolation_tactic.md
│   ├── kyc_fraud.md
│   ├── money_never.md
│   └── reporting.md
└── app/
    ├── __init__.py
    ├── main.py                  # FastAPI app entrypoint, CORS, rate limiting, router mounting
    ├── config.py                # Pydantic Settings (env-driven configuration)
    ├── database.py              # SQLAlchemy engine + session factory
    ├── rate_limit.py            # slowapi limiter instance
    ├── seed.py                  # Demo users + synthetic fraud graph seeder
    │
    ├── api/
    │   └── routes/
    │       ├── auth.py          # POST /api/auth/register, login, GET /me
    │       ├── detection.py     # POST /api/detect/message, GET /api/identifier/lookup
    │       ├── call.py          # POST /api/call/start, /api/call/{id}/end
    │       ├── ws.py            # WebSocket /ws/call/{session_id} (live call guard)
    │       ├── decoy.py         # POST /api/decoy/session/start, WS, packages
    │       ├── reports.py       # CRUD /api/reports (RBAC-gated)
    │       ├── contacts.py      # CRUD /api/contacts
    │       ├── graph.py         # GET /api/graph, /api/graph/node/{id}, /api/authority/stats
    │       ├── evidence.py      # GET /api/evidence/{report_id} (authority-only)
    │       └── guide.py         # GET /api/guide/contacts
    │
    ├── core/
    │   ├── deps.py              # get_current_user, require_role dependency
    │   └── security.py          # JWT creation, password hashing, verification
    │
    ├── models/                  # SQLAlchemy ORM models
    │   ├── user.py              # User (role: citizen | authority)
    │   ├── call.py              # CallSession
    │   ├── report.py            # Report
    │   ├── identifier.py        # Identifier, IdentifierLink (graph edges)
    │   ├── evidence.py          # Evidence (encrypted blob + SHA-256)
    │   ├── alert.py             # Alert
    │   ├── decoy.py             # DecoyPackage
    │   └── enums.py             # Role, Verdict, ScamCategory, ScamStage, etc.
    │
    ├── schemas/                 # Pydantic request/response schemas
    │   ├── auth.py
    │   ├── detection.py
    │   └── report.py
    │
    ├── services/                # Business logic & ML services
    │   ├── stt.py               # faster-whisper streaming wrapper
    │   ├── asr_norm.py          # ASR text normalization (shared with classifiers)
    │   ├── extractor.py         # Identifier extraction (phone/UPI/account/IFSC/URL)
    │   ├── entity_extractor.py  # Extended entity extraction (agency/officer/amount)
    │   ├── call_detector.py     # Trained classifier + arc tracker + interrupt logic
    │   ├── arc_scorer.py        # Stateful scam-arc stage tracking
    │   ├── classifier.py        # Trained SMS Linear-SVM classifier
    │   ├── sms_features.py      # Engineered features for SMS model
    │   ├── detection_engine.py  # Unified message analysis + known-scammer lookup
    │   ├── text_llm.py          # Unified LLM client (Groq primary, Ollama fallback)
    │   ├── fraudster.py         # Generative scammer persona (walks the arc)
    │   ├── decoy_agent.py       # Decoy loop orchestrator
    │   ├── decoy_session.py     # Decoy session state management
    │   ├── persona.py           # Decoy character + per-role voice descriptions
    │   ├── tts_service.py       # Live TTS (Indic Parler-TTS, bf16, dedicated thread)
    │   ├── svara_tts.py         # Svara-TTS engine (vLLM/GPU real-time path)
    │   ├── llm.py               # Verdict-explanation reasoning client
    │   ├── rag.py               # ChromaDB retrieval for grounded verdicts
    │   ├── graph_service.py     # networkx fraud graph + ring clustering
    │   ├── evidence.py          # Fernet-encrypt + SHA-256 hash + store
    │   ├── intelligence.py      # Report identifier ingestion
    │   ├── intelligence_package.py  # FIR-ready evidence package builder
    │   ├── alerts.py            # Twilio trusted-contact alert (+ simulated fallback)
    │   └── demo_scripts.py      # Pre-built demo transcript sequences
    │
    ├── ml/                      # Trained model artifacts
    │   └── models/
    │       ├── call/            # Call classifier + arc tracker (joblib)
    │       └── sms/             # SMS SVM classifier (joblib)
    │
    ├── prompts/                 # LLM prompt templates
    └── data/                    # Generated/synthetic data (gitignored)
```

---

## API Endpoints

### Authentication

| Method | Path | Description | Auth | Rate Limit |
| --- | --- | --- | --- | --- |
| `POST` | `/api/auth/register` | Create user, return JWT | — | 10/min |
| `POST` | `/api/auth/login` | OAuth2 password login, return JWT | — | 20/min |
| `GET` | `/api/auth/me` | Get current authenticated user | Bearer | — |

### Detection

| Method | Path | Description | Auth | Rate Limit |
| --- | --- | --- | --- | --- |
| `POST` | `/api/detect/message` | Check a pasted SMS/WhatsApp message → grounded verdict | Bearer | 30/min |
| `GET` | `/api/identifier/lookup?value=` | Known-scammer check (the flywheel's payoff) | Bearer | 60/min |

### Call Sessions

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `POST` | `/api/call/start` | Start a new call monitoring session | Bearer |
| `POST` | `/api/call/{id}/end` | End a call session, record outcome | Bearer |

### Reports

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `POST` | `/api/reports` | File a report → identifiers ingested, contacts alerted | Bearer |
| `GET` | `/api/reports` | List reports (citizens: own; authorities: all) | Bearer |
| `GET` | `/api/reports/{id}` | Get report detail | Bearer |

### Trusted Contacts

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `GET` | `/api/contacts` | List user's trusted contacts | Bearer |
| `POST` | `/api/contacts` | Add a trusted contact | Bearer |
| `DELETE` | `/api/contacts/{id}` | Remove a trusted contact | Bearer |

### Intelligence (Authority-Only)

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `GET` | `/api/graph` | Full fraud-network graph as `{nodes, links}` | Authority |
| `GET` | `/api/graph/node/{id}` | Node detail: neighbours + linked reports | Authority |
| `GET` | `/api/authority/stats` | Dashboard stats: totals, trend, top rings | Authority |

### Evidence (Authority-Only)

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `GET` | `/api/evidence/{report_id}` | Decrypt + verify tamper-evident evidence | Authority |

### AI Decoy

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `POST` | `/api/decoy/session/start` | Start a decoy session | Bearer |
| `GET` | `/api/decoy/package/{id}` | Get intelligence package | Bearer |
| `POST` | `/api/decoy/package/{id}/submit` | Submit package as a report | Bearer |

### Guide

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| `GET` | `/api/guide/contacts?lang=` | Helpline contacts for the Stay Safe guide | Bearer |

### Health

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness probe → `{"status": "ok"}` |

---

## WebSocket Channels

### Live Call Guard: `WS /ws/call/{session_id}`

Streams real-time call analysis. The client sends audio chunks or demo tick actions;
the server responds with:

```json
{
  "partial_transcript": "...",
  "stage": "accusation",
  "confidence": 0.72,
  "verdict": "suspicious",
  "interrupt": false,
  "sources": [{"title": "...", "snippet": "..."}]
}
```

When `interrupt=true` (confidence ≥ threshold AND stage ≥ isolation), the frontend
renders the full-screen `InterruptTakeover`.

### AI Decoy: `WS /api/decoy/ws/{session_id}`

Streams the generative decoy conversation turn-by-turn:

```json
{
  "type": "caller_line|decoy_line|audio|detection|complete",
  "text": "...",
  "audio_base64": "...",
  "stage": "...",
  "confidence": 0.85,
  "identifiers": [{"type": "upi", "value": "scammer@upi"}]
}
```

---

## Services

| Service | Responsibility |
| --- | --- |
| `stt.py` | Local faster-whisper streaming. Rolling in-memory buffer; **no disk writes**. |
| `asr_norm.py` | ASR text normalization (shared with training pipelines). |
| `extractor.py` / `entity_extractor.py` | Extract phone / UPI / account / IFSC / URL / agency / officer / amount. The shared data spine. |
| `call_detector.py` | Trained on-device classifier + arc tracker; deterministic interrupt + mode decision. |
| `arc_scorer.py` | Stateful scam-arc stage tracking with monotonic enforcement. |
| `classifier.py` | Trained SMS Linear-SVM for the Fraud Shield message path. |
| `detection_engine.py` | Unified message analysis pipeline + known-scammer lookup. |
| `text_llm.py` | **Unified LLM client — Groq primary, Ollama fallback.** Powers the decoy conversation. |
| `fraudster.py` | Generative **scammer persona** — walks the scam arc, invents identifiers. |
| `decoy_agent.py` | Orchestrates the decoy loop: detection → decoy reply → both voices → evidence. |
| `persona.py` | The decoy character (personalised to the user's name) + per-role Parler voice descriptions. |
| `tts_service.py` | Live speech synthesis (Indic Parler-TTS, bf16, dedicated GPU thread) with fallbacks. |
| `svara_tts.py` | Svara-TTS engine (Orpheus-style 3B model with SNAC codec, vLLM backend). |
| `llm.py` | Verdict-explanation reasoning client (local, templated fallback). |
| `rag.py` | ChromaDB retrieval — grounds verdicts in a cited advisory. |
| `graph_service.py` | networkx fraud graph + ring clustering; feeds the flywheel. |
| `evidence.py` | Fernet-encrypt + SHA-256 hash + store; authority-only access. |
| `intelligence.py` | Ingest report identifiers into the fraud graph. |
| `intelligence_package.py` | Build the FIR-ready evidence package from a decoy call. |
| `alerts.py` | Twilio trusted-contact alert with a simulated fallback. |

---

## Database Models

| Model | Key Fields | Notes |
| --- | --- | --- |
| `User` | email, hashed_password, full_name, role | Roles: `citizen`, `authority` |
| `CallSession` | transcript, max_confidence, stage_reached, interrupted, outcome | One per monitored call |
| `Report` | channel, scam_category, content, location, status | Filed by citizens |
| `Identifier` | type, value, risk_score, report_count, first_seen | Phone / UPI / account / IFSC / URL |
| `IdentifierLink` | source_id, target_id, weight, reason | Graph edges linking co-occurring identifiers |
| `Evidence` | encrypted_blob, sha256_hash, access_role | Authority-only decryption |
| `Alert` | channel, status, simulated | Trusted-contact notifications |
| `DecoyPackage` | session data, extracted identifiers, FIR narrative | AI Decoy intelligence package |

---

## Authentication & RBAC

- **Password hashing:** `passlib` + `bcrypt` (pinned to 4.0.1 for compatibility).
- **JWT tokens:** `PyJWT` with HS256 algorithm, configurable expiry.
- **Two roles:** `citizen` and `authority`, enforced via `get_current_user` and
  `require_role` FastAPI dependencies on every protected route.
- **Rate limiting:** `slowapi` on auth and detection endpoints.
- **CORS:** Restricted to configured origins (comma-separated), never `*`.

---

## Environment Variables

All configuration is loaded from environment variables or a `.env` file at the repo
root. See `../.env.example` for the full list with comments.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `JWT_SECRET` | Yes | `change-me-...` | Secret key for JWT signing |
| `JWT_EXPIRE_MINUTES` | No | `120` | JWT token expiry |
| `EVIDENCE_KEY` | Recommended | (volatile key) | Fernet encryption key for evidence |
| `DATABASE_URL` | No | `sqlite:///./kavach.db` | Database connection string |
| `FRONTEND_ORIGIN` | No | `http://localhost:5173` | Allowed CORS origins (comma-separated) |
| `TEXT_PROVIDER` | No | `auto` | `auto` / `groq` / `ollama` |
| `GROQ_API_KEY` | For Groq | — | Groq API key for fast cloud LLM |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model name |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `gemma3:4b` | Ollama model name |
| `OLLAMA_NUM_GPU` | No | `0` | GPU layers for Ollama (0 = CPU) |
| `CALL_MODEL_DIR` | No | `app/ml/models/call` | Trained call model artifacts |
| `SMS_MODEL_DIR` | No | `app/ml/models/sms` | Trained SMS model artifacts |
| `INTERRUPT_THRESHOLD` | No | `0.7` | Deterministic interrupt confidence threshold |
| `TWILIO_ACCOUNT_SID` | For real alerts | — | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | For real alerts | — | Twilio auth token |
| `TWILIO_FROM_NUMBER` | For real alerts | — | Twilio sender number |
| `WHISPER_MODEL_SIZE` | No | `medium` | faster-whisper model size |
| `TTS_ENGINE` | No | `parler` | TTS engine: `parler` or `svara` |
| `TTS_DEVICE` | No | auto | Device override for TTS (mps → cuda → cpu) |

---

## Setup

### Prerequisites

- **Python 3.11+**
- Optional: Groq API key, Ollama, ffmpeg, Twilio trial, Parler-TTS model

### Install

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp ../.env.example ../.env    # then edit values

# Generate an evidence encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste the output into EVIDENCE_KEY in .env

# Seed demo users + synthetic fraud graph
python -m app.seed
```

### Text Generation Provider

The AI Decoy conversation is generated by an LLM. Kavach picks the provider automatically:

- **Groq (recommended, fast, cloud):** Set `GROQ_API_KEY` in `.env`. Frees the local
  GPU entirely for live speech synthesis.
- **Ollama (fully local fallback):** If no `GROQ_API_KEY` is set, Kavach automatically
  uses local Ollama. Run `ollama pull gemma3:4b` first.

### Decoy Voices (Optional)

```bash
# Parler-TTS (primary, ~2.5 GB model download)
pip install git+https://github.com/huggingface/parler-tts.git

# Svara-TTS (alternative, needs vLLM + GPU)
pip install snac
```

---

## Running

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The API is served at `http://localhost:8000`. Interactive docs at `/docs` (Swagger) and
`/redoc`.

On startup, the backend:
1. Creates database tables if missing.
2. Warms TTS models, on-device detectors, and the local LLM (non-blocking background thread).

---

## Docker

```bash
docker build -t kavach-backend .
docker run -p 8000:8000 --env-file ../.env kavach-backend
```

The Dockerfile seeds the database on first boot if it's missing, then serves via Uvicorn.

---

## Seeding Demo Data

```bash
python -m app.seed
```

Creates three demo accounts and a synthetic fraud-network graph:

| Role | Email | Password |
| --- | --- | --- |
| Citizen | citizen@kavach.demo | password123 |
| Citizen 2 | citizen2@kavach.demo | password123 |
| Authority | authority@kavach.demo | password123 |

---

## Graceful Degradation

Kavach is designed so a **fresh clone runs with no Groq key, no Ollama, no Twilio, and
no TTS model** — each has a working fallback, and nothing 500s.

| Dependency | If Missing |
| --- | --- |
| Groq API key | Falls back to local Ollama |
| Ollama | Decoy uses templated responses |
| Parler-TTS / Svara-TTS | Decoy runs text-only (no audio) |
| faster-whisper | Live-mic disabled; demo mode works |
| Twilio | Alerts are simulated and logged |
| ChromaDB / sentence-transformers | Verdicts returned without RAG citation |
| Trained ML models | Rule-based fallback scorers |
| Evidence key | Volatile key generated at startup |

Each router is mounted defensively — a module that fails to import logs a warning
instead of taking the whole app down.
