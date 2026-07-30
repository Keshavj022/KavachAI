# Kavach AI — Digital Arrest & Fraud Shield

> **Kavach** (Sanskrit: *armour*) is a two-sided AI platform that protects people from
> "digital arrest" and phone-fraud scams — and turns every rescue into intelligence
> that protects the next person.

A victim in the grip of a digital-arrest scam will **never** stop to open an app and
ask *"is this a scam?"* — the scam is engineered to disable their judgement. So Kavach
does not wait to be asked. It **watches, decides, and interrupts on the victim's
behalf**, and — when needed — **answers the scammer for them**.

---

## Table of contents

- [The problem](#the-problem)
- [The solution](#the-solution)
- [Signature moments](#signature-moments-what-a-judge-remembers)
- [Feature overview](#feature-overview)
- [Architecture](#architecture)
- [How it works (workflows)](#how-it-works-workflows)
- [Component guide](#component-guide)
- [Tech stack](#tech-stack)
- [What's real vs. simulated](#whats-real-vs-simulated)
- [Getting started](#getting-started)
- [Privacy & security](#privacy--security)
- [The on-device detection models](#the-on-device-detection-models)
- [Multilingual support](#multilingual-support)
- [Future enhancements](#future-enhancements)
- [Repository layout](#repository-layout)

---

## The problem

"Digital arrest" is the fastest-growing cyber-crime in India. A fraudster impersonates
the police, CBI, or ED over a call or video call, terrifies the victim with a fabricated
criminal case, **isolates** them ("stay on the line, tell no one, this is confidential"),
and coerces them into transferring money — often their entire life savings. Indians lost
**thousands of crores of rupees** to these scams, with a single victim frequently losing
lakhs to crores.

The cruelty of the scam is psychological. It is a **script that follows a predictable
arc** — authority claim → accusation → isolation → money demand — and it works by keeping
the victim in a state of panic where rational thought, and "let me check with someone,"
become impossible.

Two facts shape everything Kavach does:

1. **The victim cannot be the one who acts.** Any tool that requires the frightened person
   to open an app and ask for help has already lost. Protection must be *passive*.
2. **Every scam call is a data point.** The same numbers, UPI IDs, and mule accounts are
   reused across hundreds of victims. If the network remembers, the next victim can be
   warned *instantly*.

---

## The solution

Kavach is a **passive guardian** with a **collective-intelligence flywheel**.

**Consumer side** — a phone-framed app that:

- **Watches a call live**, transcribes it on-device, scores it against the scam arc, and
  the moment confidence crosses a threshold **at the isolation stage — before any money is
  demanded** — takes over the screen with a calm, full-bleed warning that breaks the
  victim's trance.
- **Answers scam calls for the user with an AI Decoy** — a generative agent that plays a
  flustered, cooperative version of the user, wastes the scammer's time, and extracts their
  UPI IDs, accounts, and amounts into an evidence package.
- **Checks suspicious SMS/WhatsApp messages** in a Fraud Shield chat.
- **Teaches** via a five-chapter, multilingual "Stay Safe" guide.
- **Files a pre-filled report** and **alerts a trusted contact** — breaking the isolation
  the scammer depends on.

**Authority side** — a command center that turns those reports into:

- a **live case feed**,
- a **fraud-network graph** where numbers, UPI IDs, and accounts cluster into rings,
- a **geospatial hotspot map**, and
- **tamper-evident, encrypted evidence** accessible only to authorities.

### The flywheel — the core thesis

```
   One citizen reports a scammer's number/UPI/account
                     │
                     ▼
        It is written into the fraud graph
                     │
                     ▼
   The next citizen contacted by that identifier gets
   an INSTANT known-scammer verdict — no ML needed,
        because the network already knows it.
```

Individual protection feeds collective intelligence, which sharpens individual protection.

---

## Signature moments (what a judge remembers)

1. **The interrupt that fires *before* the money is demanded.** The confidence meter climbs
   through the arc; at *isolation*, the screen slams into a red, authoritative, de-escalating
   takeover — while the victim can still be saved.
2. **The AI Decoy answering the scammer live.** Two AI voices — the fraudster and the decoy —
   hold a completely improvised Hindi conversation. Every call is different. The scammer's
   UPI ID and demanded amount appear as evidence chips in real time.
3. **The number lighting up in a fraud ring.** A report filed on the consumer side appears
   seconds later on the authority dashboard, and the scammer's identifiers glow inside a
   cluster on the force-directed graph.

---

## Feature overview

### Consumer app (calm, accessible, phone-framed)

| Feature | What it does |
| --- | --- |
| **Live Call Guard** | Transcribes a call on-device, scores the scam arc, fires a full-screen **interrupt** at the isolation stage. Confidence meter + stage labels animate live. |
| **AI Decoy** | A generative agent answers the call *as the user*, plays both a **fraudster** and a **decoy** via the LLM, voices both sides live, and extracts an evidence package. |
| **Fraud Shield chat** | Paste a suspicious SMS/WhatsApp message → grounded verdict, red flags, cited source, and an instant known-scammer check. |
| **Guided reporting** | One-tap, pre-filled report to a mock 1930 / cybercrime.gov.in intake. |
| **Trusted-contact alert** | SMS to a family member on a confirmed scam (real via Twilio, or simulated-and-logged) — breaks the scammer's isolation. |
| **Stay Safe guide** | Five-chapter visual walkthrough: the scam arc, the five words that end any scam call, legal rights with citations, the first-hour recovery sequence, and a shareable emergency card. |
| **12 languages** | Full UI i18n incl. right-to-left Urdu, lazy per-script font loading. |

### Authority command center (dark, data-dense)

| Feature | What it does |
| --- | --- |
| **Dashboard** | Live case count, active alerts, stat cards, recent reports feed. |
| **Fraud Graph** | Force-directed graph of identifiers clustered into rings; click a node for its links and reports. |
| **Hotspot Map** | Leaflet + OpenStreetMap map of reported-crime density. |
| **Reports & Case detail** | Paginated reports table with RBAC; per-case detail view. |
| **Encrypted evidence** | Authority-only decryption of the tamper-evident evidence segment (citizens get 403). |

---

## Architecture

Kavach is three logical layers over one shared backend and datastore.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  INTERFACE / SENSOR LAYER                                                      │
│  Consumer app (phone frame): Live Call Guard · AI Decoy · Fraud Shield ·       │
│  Report · Trusted Contacts · Stay Safe guide        Authority command center   │
└───────────────┬────────────────────────────────────────────────┬─────────────┘
                │ WebSocket (live call / decoy)   REST + WS        │ REST
                ▼                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  DETECTION / CLASSIFICATION LAYER  (the brain)                                 │
│  Whisper STT → identifier extraction → known-scammer lookup →                  │
│  trained classifier → stateful ARC scorer → deterministic interrupt rule →     │
│  LLM reasoning (Groq / Ollama) + RAG grounding (ChromaDB) → Verdict            │
│  AI Decoy loop: LLM fraudster ⇄ LLM decoy, both voiced live (Parler-TTS)       │
└───────────────┬────────────────────────────────────────────────┬─────────────┘
                │ identifiers + verdict                            │ evidence
                ▼                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  INTELLIGENCE / MEMORY LAYER                                                   │
│  Fraud-network graph (networkx) · Reports store · Encrypted evidence           │
│  Feeds the authority dashboard AND feeds known-scammer context back to the     │
│  detector (the flywheel).                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Data spine.** A shared **identifier-extraction** step (phone / UPI / account / IFSC / URL)
is the seam both the detector and the graph depend on. One `Verdict` object is enriched as it
flows through the layers; one SQLite datastore (designed for a trivial swap to Postgres).

**Graceful degradation is a design principle.** A fresh clone runs with **no Groq key, no
Ollama, no Twilio, and no TTS model** — each has a working fallback, and nothing 500s.

---

## How it works (workflows)

### 1. Live Call Guard — the interrupt

```
audio chunk / demo tick
   → local Whisper transcribe (rolling in-memory buffer, discarded)
   → identifier extraction  → known-scammer lookup (instant verdict if hit)
   → trained classifier (scam probability + category)
   → stateful ARC scorer  (authority_claim → accusation → isolation → money_demand)
   → deterministic interrupt rule:  fire IF confidence ≥ threshold AND stage ≥ isolation
   → LLM explanation + RAG-cited source  →  Verdict streamed over WebSocket
```

The interrupt decision is made **in code, not by a model** (`INTERRUPT_THRESHOLD`) — so it
is auditable and thresholdable. The de-escalation copy is a **pre-written, reviewed
template**; the LLM never authors safety-critical text.

### 2. AI Decoy — a fully generated scam call

```
Scenario picker seeds only the framing (digital-arrest / tech-support).
Then, per turn, the SAME LLM plays BOTH sides:

  FRAUDSTER (LLM)  walks the arc, invents an officer name, and drops a fake
      UPI/account/amount at the money beat
        → detection + identifier extraction on the generated text
        → caller voice synthesized live (Parler-TTS)  ─┐
                                                         │ streamed as it's ready
  DECOY (LLM)  answers AS THE USER (by real name), plays confused, stalls
        → decoy voice synthesized live (a DIFFERENT voice) ─┘

  → confidence meter climbs, evidence chips appear, verdict + intelligence
    package generated on a confirmed scam.
```

Nothing is scripted. Every call is different text, different voices, in Devanagari Hindi.
The two speakers use **audibly different voices**, and the frontend plays them back as a
**sequential queue** so the transcript and meter stay locked to the audio.

### 3. The flywheel — collective intelligence

```
Citizen A files a report  →  identifiers written to the fraud graph
Authority sees the case + the ring on the graph
Citizen B is contacted by the same number  →  known-scammer lookup returns an
    INSTANT verdict, before any ML runs.
```

---

## Component guide

### Backend services (`backend/app/services/`)

| Component | Responsibility |
| --- | --- |
| `stt.py` | Local faster-whisper streaming wrapper. Rolling in-memory buffer; **no disk writes**. |
| `extractor.py` / `entity_extractor.py` | Extract phone / UPI / account / IFSC / URL / agency / officer / amount. The shared data spine. |
| `call_detector.py` | Trained on-device classifier + arc tracker; deterministic interrupt + mode decision. |
| `classifier.py` | Trained SMS Linear-SVM for the Fraud Shield message path. |
| `text_llm.py` | **Unified LLM client — Groq primary, Ollama fallback.** Powers the decoy conversation. |
| `fraudster.py` | Generative **scammer persona** — walks the scam arc, invents identifiers. |
| `decoy_agent.py` | Orchestrates the decoy loop: detection → decoy reply → both voices → evidence. |
| `persona.py` | The decoy character (personalised to the user's name) + per-role Parler voice descriptions. |
| `tts_service.py` | Live speech synthesis (Indic Parler-TTS, bf16, dedicated GPU thread) with fallbacks. |
| `llm.py` | Verdict-explanation reasoning client (local, templated fallback). |
| `rag.py` | ChromaDB retrieval — grounds verdicts in a cited advisory. |
| `graph_service.py` | networkx fraud graph + ring clustering; feeds the flywheel. |
| `evidence.py` | Fernet-encrypt + SHA-256 hash + store; authority-only access. |
| `alerts.py` | Twilio trusted-contact alert with a simulated fallback. |
| `intelligence_package.py` | Builds the FIR-ready evidence package from a decoy call. |

### Frontend (`frontend/src/`)

| Area | What's there |
| --- | --- |
| `pages/consumer/` | Live Call, AI Decoy, Fraud Shield chat, Report, Contacts, Stay Safe guide. |
| `pages/authority/` | Dashboard, Fraud Graph, Reports table, Case detail, Hotspot Map. |
| `components/InterruptTakeover.tsx` | **The signature interrupt** — full-bleed red takeover (framer-motion). |
| `components/ConfidenceMeter.tsx` | Animated arc meter that climbs green → amber → red through the arc. |
| `components/DecoyLiveView.tsx` | The live decoy call view — waveform, chips, dual-voice transcript. |
| `i18n/` | 12-language react-i18next setup, lazy Noto fonts, RTL. |
| `store/` | zustand stores (auth, live-call session). |

### ML training (`call_classifier/`, `sms_classifier/`)

Reproducible pipelines that build the on-device models from audited public datasets, with
an honest metrics report (`call_classifier/reports/REPORT.md`).

---

## Tech stack

| Layer | Technologies |
| --- | --- |
| **Backend** | Python 3.11, FastAPI, Uvicorn (ASGI), native WebSockets, SQLAlchemy 2.x + SQLite, Pydantic v2 |
| **Auth / security** | PyJWT (HS256), passlib/bcrypt, RBAC, slowapi rate limiting, CORS |
| **Speech-to-text** | faster-whisper (local, streaming) |
| **Detection ML** | scikit-learn (TF-IDF + LogReg call classifier, arc tracker, SMS SVM); rule-based fallbacks |
| **LLM (decoy + fraudster)** | **Groq** (`llama-3.3-70b-versatile`) primary · **Ollama** (`gemma3:4b`) local fallback |
| **Text-to-speech** | AI4Bharat **Indic Parler-TTS** (bf16, live) · optional Svara-TTS (vLLM/GPU) |
| **RAG / embeddings** | sentence-transformers + ChromaDB |
| **Graph** | networkx (in-memory, from DB identifiers) |
| **Crypto** | cryptography (Fernet/AES) + hashlib (SHA-256) |
| **Alerts** | Twilio (simulated fallback) |
| **Frontend** | React 18 + TypeScript + Vite, Tailwind, react-router, zustand, framer-motion, react-force-graph-2d, recharts, react-leaflet, react-i18next, lucide-react |

---

## What's real vs. simulated

Kavach is honest about its boundaries — live OS/telecom call interception is restricted on
real phones, so a few edges are simulated. **Everything else is real code.**

| Simulated (prototype boundary) | Real (working code) |
| --- | --- |
| The incoming "call" audio (Demo mode transcript, browser mic, or the **LLM-generated scammer** in the decoy) | On-device STT, detection, arc scoring, the interrupt decision |
| Reporting to 1930 / Chakshu (a mock intake endpoint) | The full report lifecycle, RBAC, evidence encryption |
| The fraud graph's seed data (synthetic-but-realistic rings) | The graph build, ring clustering, and known-scammer flywheel |

The production path — Android `CallScreeningService`, telecom-layer DoT DIP integration,
official Chakshu/1930 intake APIs — is described where relevant and never obscured in the UI.

---

## Getting started

### Prerequisites

- **Node.js 20+** and **Python 3.11+**
- Optional but recommended: a **[Groq](https://console.groq.com) API key** for fast cloud
  text generation (see below). Without it, the app falls back to local **[Ollama](https://ollama.com)**.
- Optional: **`ffmpeg`** (live-mic path), a **Twilio** trial (real alerts), the **Parler-TTS**
  model (decoy voices).

### 1. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp ../.env.example ../.env          # then edit values
# Generate an evidence key and paste it into EVIDENCE_KEY in .env:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Seed demo users + the synthetic fraud graph
python -m app.seed

# Run
uvicorn app.main:app --reload --port 8000
```

### 2. Text generation — Groq (recommended) or Ollama (fallback)

The AI Decoy conversation (both the fraudster and the decoy) is generated by an LLM. Kavach
picks the provider automatically:

- **Groq (recommended, fast, cloud).** Set `GROQ_API_KEY` in `.env`. Text is generated in
  ~1–2 s by `llama-3.3-70b-versatile`, and — crucially on a laptop — the local GPU stays
  **entirely free for live speech synthesis**. This is the smoothest demo path.

  ```bash
  # in .env
  GROQ_API_KEY=gsk_your_key_here
  TEXT_PROVIDER=auto            # 'auto' uses Groq when the key is present
  ```

- **Ollama (fully local fallback).** If **no `GROQ_API_KEY` is set**, Kavach automatically
  uses local Ollama instead — nothing leaves the machine. Install Ollama, pull the model,
  and keep it running:

  ```bash
  ollama pull gemma3:4b
  # in .env (optional overrides):
  # TEXT_PROVIDER=ollama        # force local even if a Groq key exists
  # OLLAMA_NUM_GPU=0            # run the LLM on CPU so the GPU is free for TTS
  ```

You can force either provider with `TEXT_PROVIDER=groq` or `TEXT_PROVIDER=ollama`.

### 3. Decoy voices (optional but recommended)

Install Indic Parler-TTS to hear both sides of the decoy call. Every line is synthesized
**live** (nothing pre-recorded); the model warms at startup.

```bash
cd backend && source venv/bin/activate
pip install git+https://github.com/huggingface/parler-tts.git   # ~2.5 GB model
```

Runs in bf16 on Apple **MPS** by default (then CUDA, then CPU; override with `TTS_DEVICE`).
Without it, the decoy still runs and shows the lines as text.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

### 5. Docker (alternative)

```bash
docker compose up --build
# frontend: http://localhost:5173   backend: http://localhost:8000
```

### Demo accounts

| Role      | Email                   | Password    |
| --------- | ----------------------- | ----------- |
| Citizen   | citizen@kavach.demo     | password123 |
| Citizen 2 | citizen2@kavach.demo    | password123 |
| Authority | authority@kavach.demo   | password123 |

### The 3-minute demo walkthrough

1. **Sign in as the citizen.** The app opens in a phone frame.
2. **Live Call Guard.** On **Call**, pick "Digital arrest" and start. The confidence meter
   climbs through the arc; at the **isolation** stage the **interrupt** takes over the screen.
3. **Grounded verdict + report.** Dismiss it, review the cited source, file the pre-filled
   report in one tap. A trusted contact is alerted.
4. **AI Decoy.** Open **Decoy**, simulate an incoming call, and **Let Kavach talk** — hear the
   fully generated scam conversation, watch identifiers become evidence chips, and get the
   intelligence package + verdict.
5. **Switch to the authority login.** The report is in the live feed, and the scammer's number
   is glowing inside a ring on the **Fraud Graph**.
6. **Prove the flywheel.** As a second citizen, check that same number in **Fraud Shield** —
   an instant known-scammer verdict, because the network already knows it.

---

## Privacy & security

Privacy is a first-class feature, not an afterthought.

- **Audio is never stored.** It is processed in a rolling in-memory buffer and discarded
  continuously (`services/stt.py`). Live-mic audio is transcribed locally; only text leaves
  the browser. The Web Speech API is deliberately avoided because it uploads audio.
- **Evidence is preserved only on a confirmed scam**, then **Fernet/AES-encrypted**,
  **SHA-256 hashed** for tamper-evidence, and gated to the **authority role only**. The
  citizen who was recorded can never download it — this removes the misuse incentive that
  got call recording locked down on modern phones.
- **Auth & RBAC.** bcrypt password hashing, JWT (HS256) access tokens, and two roles
  (`citizen` / `authority`) enforced on every protected route.
- **Hardening.** CORS restricted to configured origins, rate limiting on auth + detection
  endpoints, Pydantic validation at every boundary, no secrets in the repo.
- **Cloud boundary.** With Groq enabled, the decoy/fraudster **transcript** is sent to Groq
  for text generation. For a fully on-device deployment, set `TEXT_PROVIDER=ollama` — then
  the entire pipeline (STT, detection, generation, synthesis) runs locally.

---

## The on-device detection models

The call and message classifiers are **trained, local, and deterministic** — there is **no
network call in the runtime detection path** (regardless of the text-generation provider).

- **Call path:** local Whisper → `asr_normalize()` → trained TF-IDF + Logistic-Regression
  classifier → trained arc tracker (per-chunk stage classifier with a deterministic cue
  backstop) → the deterministic interrupt rule → a pre-written de-escalation template.
- **Message path:** trained SMS Linear-SVM (threshold 0.505), behind the known-scammer graph
  lookup as a fast path.
- **Honest metrics:** `call_classifier/reports/REPORT.md` reports a 0% false-positive rate on
  real legitimate call-center calls and reports the synthetic→real recall drop plainly. A
  known limitation — the SMS model false-positives on legitimate transactional SMS — is left
  visible with a trusted-sender allowlist hook stubbed in `classifier.py`.

The trained artifacts ship in `backend/app/ml/models/{call,sms}` so the app runs out of the
box; `call_classifier/` and `sms_classifier/` reproduce them from scratch.

---

## Multilingual support

The consumer UI is fully multilingual via `react-i18next` — **12 languages**: English, Hindi,
Bengali, Telugu, Marathi, Tamil, Gujarati, Kannada, Malayalam, Punjabi, Odia, and Urdu (which
switches the whole layout to right-to-left). Language persists in `localStorage`; the correct
Noto font for each script loads lazily.

The **Stay Safe** guide (`/app/guide`) is a five-chapter visual walkthrough — the scam arc,
the five words that end any scam call, legal rights with citations, the first-hour recovery
sequence, and a shareable emergency-contact card exported as a retina PNG in the active
language. Every helpline, portal, and legal citation was verified against official Government
of India sources and is served from `GET /api/guide/contacts`.

---

## Future enhancements

Kavach is a working prototype with a clear path to a production-grade public-safety system.

**A complete, self-serve control application.** A full admin/control app (web + mobile) that
puts *everything* under the user's and authority's control from one place: enrolling and
managing protected numbers and trusted contacts, configuring interrupt sensitivity and
languages per user, choosing and previewing decoy personas and voices, reviewing and
exporting evidence, and a live operations console for authorities to manage cases, tune the
fraud-graph clustering, and push takedown requests.

**On-device, OS-level interception.** Ship the real capture path — an Android
`CallScreeningService` / iOS CallKit app and a telecom-layer integration (DoT Digital
Intelligence Platform) — so Kavach guards actual cellular calls, not a simulated feed.

**Live authority integrations.** Real submission to the Chakshu / 1930 / Sanchar Saathi
intake APIs, and a privacy-preserving **federated fraud graph** shared across telecoms and
banks so a mule account flagged in one place is blocked everywhere.

**Instant financial circuit-breakers.** UPI/bank integration to auto-initiate a transaction
freeze or reversal window the moment a scam is confirmed — the RBI zero-liability reporting
clock starts automatically.

**Deepfake-aware, multi-modal detection.** Digital-arrest scams increasingly use fake police
"video calls." Add on-device face/voice deepfake detection and fake-uniform/badge recognition
to the arc scorer.

**Sub-second streaming voice + voice consent.** Stream TTS audio token-by-token for near-zero
latency, and (with explicit consent) let the decoy answer in a voice the user chooses.

**Smaller, faster, everywhere.** Quantized on-device models for low-end phones, a WhatsApp/SMS
bot channel for message checking, and elder-first accessibility (large type, screen-reader
support, one-tap "call my son" from the interrupt).

**Analytics for authorities.** Predictive hotspot forecasting, ring-growth trend detection,
model-drift monitoring, and an explainability view for every verdict — moving the authority
side from reactive to proactive.

**Scale.** Swap SQLite → Postgres and the in-memory graph → Neo4j (both designed for), and a
horizontally-scalable detection service.

---

## Repository layout

```
kavach/
├── backend/            FastAPI app, detection + decoy services, ML models, RAG corpus
│   ├── app/
│   │   ├── api/routes/  auth, detection, call (ws), decoy (ws), reports, graph, evidence…
│   │   ├── services/    stt, extractor, call_detector, text_llm, fraudster, decoy_agent,
│   │   │                persona, tts_service, rag, graph_service, evidence, alerts…
│   │   ├── ml/models/   trained call + SMS artifacts (ship in-repo)
│   │   └── models/ schemas/ core/   SQLAlchemy models, Pydantic schemas, auth + deps
├── frontend/           React + TS + Vite — consumer (phone) and authority (command center)
├── call_classifier/    reproducible call-scam model training + honest metrics report
├── sms_classifier/     reproducible SMS model training
├── ARCHITECTURE.md     detailed architecture + a diagram-generation prompt
└── README.md
```

---

*Kavach is a hackathon prototype built to demonstrate a real, deployable approach to
digital-arrest fraud protection. The two moments to remember: the **interrupt that fires
before the money is demanded**, and the **number lighting up in a fraud ring**.*
