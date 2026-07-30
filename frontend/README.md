# Kavach AI — Frontend

> React + TypeScript SPA powering two distinct interfaces: a **consumer app** (rendered
> inside a phone frame) for citizens, and an **authority command center** (dark, data-dense)
> for law enforcement. 12-language support including RTL Urdu.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Routes & Pages](#routes--pages)
- [Components](#components)
- [State Management](#state-management)
- [API & WebSocket Integration](#api--websocket-integration)
- [Internationalization (i18n)](#internationalization-i18n)
- [Design System](#design-system)
- [Environment Variables](#environment-variables)
- [Setup](#setup)
- [Scripts](#scripts)
- [Docker](#docker)

---

## Tech Stack

| Category | Technology |
| --- | --- |
| **Framework** | React 18.3 + TypeScript |
| **Build Tool** | Vite 6 |
| **Routing** | react-router-dom v6 |
| **State Management** | zustand v5 |
| **Styling** | Tailwind CSS 3.4 + PostCSS + Autoprefixer |
| **Animations** | framer-motion v11 |
| **Data Visualization** | recharts (charts), react-force-graph-2d (fraud graph) |
| **Maps** | leaflet + react-leaflet (hotspot map) |
| **Internationalization** | i18next + react-i18next (12 languages, RTL) |
| **Icons** | lucide-react |
| **Screenshot Export** | html2canvas (Stay Safe guide cards) |
| **Production Server** | Nginx (Docker) |

---

## Project Structure

```
frontend/
├── Dockerfile                      # Multi-stage: Vite build → Nginx Alpine
├── nginx.conf                      # SPA fallback configuration
├── index.html                      # HTML shell
├── package.json
├── vite.config.ts                  # Dev server config (port 5173)
├── tailwind.config.js              # Dual-audience design tokens
├── tsconfig.json
├── postcss.config.js
├── scripts/
│   └── translate_guide.mjs         # Locale translation helper (Ollama)
└── src/
    ├── main.tsx                    # Entry point (BrowserRouter + i18n init)
    ├── App.tsx                     # Route tree + role guards
    ├── index.css                   # Global styles + reduced-motion support
    ├── vite-env.d.ts
    │
    ├── api/
    │   ├── client.ts               # Typed fetch wrapper with Bearer auth
    │   ├── types.ts                # Shared API response types
    │   └── decoyTypes.ts           # Decoy WebSocket frame types
    │
    ├── store/
    │   ├── auth.ts                 # Auth store (user, token, login/register/logout)
    │   └── call.ts                 # Call context store (pass detection to ReportForm)
    │
    ├── i18n/
    │   ├── config.ts               # i18next configuration
    │   ├── fonts.ts                # Dynamic Noto font loader per script
    │   ├── languages.ts            # Language definitions (12 languages)
    │   └── locales/                # Translation JSON files
    │       ├── en.json             # English
    │       ├── hi.json             # Hindi
    │       ├── bn.json             # Bengali
    │       ├── te.json             # Telugu
    │       ├── mr.json             # Marathi
    │       ├── ta.json             # Tamil
    │       ├── gu.json             # Gujarati
    │       ├── kn.json             # Kannada
    │       ├── ml.json             # Malayalam
    │       ├── pa.json             # Punjabi
    │       ├── or.json             # Odia
    │       └── ur.json             # Urdu (RTL)
    │
    ├── components/
    │   ├── Brand.tsx               # Kavach shield glyph + branding
    │   ├── PhoneFrame.tsx          # Phone bezel wrapper for consumer app
    │   ├── LanguageToggle.tsx      # Language switcher dropdown
    │   ├── ConfidenceMeter.tsx     # Animated SVG arc gauge (green→amber→red)
    │   ├── VerdictBadge.tsx        # Color-blind safe verdict pill
    │   ├── InterruptTakeover.tsx   # 🔴 Full-bleed red scam interrupt screen
    │   ├── IncomingCallInterstitial.tsx  # Simulated incoming call overlay
    │   ├── DecoyLiveView.tsx       # Live decoy: waveform, chips, dual transcript
    │   ├── ScamVerdictScreen.tsx   # Post-decoy summary + evidence + reporting
    │   ├── IntelligencePackageCard.tsx  # FIR-ready evidence card
    │   ├── Placeholder.tsx         # Loading placeholder
    │   └── guide/
    │       └── Characters.tsx      # SVG character illustrations (Raju, Priya, etc.)
    │
    ├── pages/
    │   ├── auth/
    │   │   ├── Login.tsx           # Login page (demo account quick-fill)
    │   │   └── Register.tsx        # Registration page (role selection)
    │   │
    │   ├── consumer/               # Citizen-facing pages (inside PhoneFrame)
    │   │   ├── ConsumerLayout.tsx  # Bottom nav + phone frame wrapper
    │   │   ├── LiveCall.tsx        # Live Call Guard (demo scenarios + mic)
    │   │   ├── DecoyCallView.tsx   # AI Decoy call interface
    │   │   ├── ShieldChat.tsx      # Fraud Shield: paste message → verdict
    │   │   ├── ReportForm.tsx      # Guided report filing (pre-filled)
    │   │   ├── Contacts.tsx        # Trusted contacts management
    │   │   └── GuideView.tsx       # 5-chapter Stay Safe guide
    │   │
    │   └── authority/              # Law enforcement pages (lazy-loaded)
    │       ├── AuthorityLayout.tsx  # Sidebar nav + dark theme
    │       ├── Dashboard.tsx       # Live stats, trend chart, category breakdown
    │       ├── FraudGraph.tsx      # Force-directed fraud ring graph
    │       ├── ReportsTable.tsx    # Searchable reports table
    │       ├── CaseDetail.tsx      # Single report detail + identifiers
    │       ├── HotspotMap.tsx      # Leaflet geographic hotspot map
    │       ├── EvidencePanel.tsx   # Authority-only decrypted evidence
    │       └── format.ts           # Date/number formatting utilities
    │
    ├── hooks/                      # Custom hooks (extensibility)
    └── theme/                      # Theme utilities (extensibility)
```

---

## Routes & Pages

### Public Routes

| Path | Component | Description |
| --- | --- | --- |
| `/login` | `Login` | OAuth2 login with demo account quick-fill buttons |
| `/register` | `Register` | User registration with role selection (citizen / authority) |

### Consumer Portal (`/app`) — Requires `citizen` role

All consumer pages render inside a `PhoneFrame` bezel to simulate a mobile experience.

| Path | Component | Description |
| --- | --- | --- |
| `/app` | `LiveCall` | **Live Call Guard** — demo scenarios or live mic streaming via WebSocket. Confidence meter + stage labels animate live. When the interrupt fires, `InterruptTakeover` renders. |
| `/app/decoy` | `DecoyCallView` | **AI Decoy** — simulated incoming call → Kavach answers as the user. Live waveform, dual-voice transcript, evidence chips appear in real-time. |
| `/app/shield` | `ShieldChat` | **Fraud Shield** — paste a suspicious SMS/WhatsApp message → grounded verdict with red flags and cited sources. |
| `/app/report` | `ReportForm` | **Guided Reporting** — pre-filled from detection context, one-tap submit. Triggers trusted-contact alert. |
| `/app/contacts` | `Contacts` | **Trusted Contacts** — manage family/friend numbers alerted on confirmed scams. |
| `/app/guide` | `GuideView` | **Stay Safe Guide** — 5-chapter visual walkthrough with SVG illustrations. Exportable emergency card as retina PNG. |

### Authority Portal (`/authority`) — Requires `authority` role, lazy-loaded

| Path | Component | Description |
| --- | --- | --- |
| `/authority` | `Dashboard` | Live command dashboard: case count, active alerts, 7-day trend chart, category breakdown, recent reports feed. |
| `/authority/graph` | `FraudGraph` | Interactive 2D force-directed fraud-network graph. Click nodes for neighbours and linked reports. |
| `/authority/reports` | `ReportsTable` | Paginated, searchable reports table with RBAC. |
| `/authority/reports/:id` | `CaseDetail` | Per-case detail: identifiers, verdict, evidence hash, linked reports. |
| `/authority/map` | `HotspotMap` | Leaflet + OpenStreetMap hotspot map of reported-crime density across India. |

### Route Guards

- `RequireRole` — redirects unauthenticated users to `/login`, or cross-role users to their correct home.
- `RedirectIfAuthed` — sends logged-in users away from auth pages to their role's home.
- Authority views are **lazy-loaded** (`React.lazy`) so the consumer bundle stays small.

---

## Components

### Signature Components

| Component | Description |
| --- | --- |
| `InterruptTakeover` | **The signature interrupt.** Full-bleed red overlay with `framer-motion` animation that breaks the victim's trance. Calm, authoritative, de-escalating copy. |
| `ConfidenceMeter` | Semicircular SVG gauge with 4-stage stepper (Authority → Accusation → Isolation → Money). Animates from green → amber → red. |
| `DecoyLiveView` | Real-time decoy call view: audio waveform, agent status indicators, extracted identifier evidence chips, and rolling dual-voice transcript. |
| `ScamVerdictScreen` | Post-decoy summary: call duration, extracted evidence, full transcript, one-tap report filing to 1930/Chakshu. |

### Reusable Components

| Component | Description |
| --- | --- |
| `PhoneFrame` | Phone bezel wrapper enclosing the consumer app for laptop display. |
| `Brand` | Kavach shield glyph + typography, adapts to consumer/authority themes. |
| `LanguageToggle` | Language switcher dropdown displaying native script names. |
| `VerdictBadge` | Color-blind safe verdict pill (Safe / Suspicious / Scam) with icon + label. |
| `IncomingCallInterstitial` | Simulated incoming call ringing overlay for the decoy flow. |
| `IntelligencePackageCard` | Formatted evidence card: identifiers, FIR-ready narrative, SHA-256 hashes. |
| `guide/Characters` | Custom SVG character illustrations (RajuUncle, Priya, Scammer, Son) with dynamic facial expressions. |

---

## State Management

Two **zustand** stores manage client-side state:

### `auth.ts` — Authentication Store

- `user`, `token`, `role`, `initialized` state
- `login()`, `register()`, `logout()` actions
- Token persisted in `localStorage` (`kavach_token`)
- `loadSession()` restores session on page load via `/api/auth/me`

### `call.ts` — Call Context Store

- Passes detection outcome (sessionId, channel, category, redFlags, sources, identifiers) from `LiveCall` → `ReportForm` for seamless pre-filling.

---

## API & WebSocket Integration

### HTTP Client (`api/client.ts`)

Typed `fetch` wrapper that automatically attaches `Bearer` token from the auth store.

| Category | Endpoints Called |
| --- | --- |
| **Auth** | `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/auth/me` |
| **Detection** | `POST /api/detect/message`, `GET /api/identifier/lookup` |
| **Call** | `POST /api/call/start`, `POST /api/call/{id}/end` |
| **Reports** | `GET /api/reports`, `POST /api/reports`, `GET /api/reports/{id}` |
| **Contacts** | `GET /api/contacts`, `POST /api/contacts`, `DELETE /api/contacts/{id}` |
| **Authority** | `GET /api/graph`, `GET /api/graph/node/{id}`, `GET /api/authority/stats`, `GET /api/evidence/{reportId}` |
| **Decoy** | `POST /api/decoy/session/start`, `GET /api/decoy/package/{id}`, `POST /api/decoy/package/{id}/submit` |
| **Guide** | `GET /api/guide/contacts?lang=` |

### WebSocket Channels

| Channel | Path | Purpose |
| --- | --- | --- |
| **Live Call Guard** | `WS_BASE/ws/call/{session_id}` | Streams audio chunks / demo actions → receives transcript, stage, confidence, interrupt trigger |
| **AI Decoy** | `WS_BASE/api/decoy/ws/{session_id}` | Streams turn-by-turn spoken lines, audio clips, detection metadata, call completion frames |

---

## Internationalization (i18n)

Full UI i18n via `react-i18next` — **12 languages**:

| Language | Code | Script | Font |
| --- | --- | --- | --- |
| English | `en` | Latin | System default |
| Hindi | `hi` | Devanagari | Noto Sans Devanagari |
| Bengali | `bn` | Bengali | Noto Sans Bengali |
| Telugu | `te` | Telugu | Noto Sans Telugu |
| Marathi | `mr` | Devanagari | Noto Sans Devanagari |
| Tamil | `ta` | Tamil | Noto Sans Tamil |
| Gujarati | `gu` | Gujarati | Noto Sans Gujarati |
| Kannada | `kn` | Kannada | Noto Sans Kannada |
| Malayalam | `ml` | Malayalam | Noto Sans Malayalam |
| Punjabi | `pa` | Gurmukhi | Noto Sans Gurmukhi |
| Odia | `or` | Odia | Noto Sans Oriya |
| Urdu | `ur` | Nastaliq | Noto Nastaliq Urdu |

- **RTL support:** Urdu switches the entire layout to right-to-left.
- **Lazy font loading:** Noto fonts are loaded on-demand per script via `fonts.ts`.
- **Language persistence:** Selection saved in `localStorage`.

---

## Design System

Tailwind is configured with a dual-audience design token system in `tailwind.config.js`:

### Consumer Theme (Light, Calm, Trust-Forward)

| Token | Value | Purpose |
| --- | --- | --- |
| `consumer-bg` | `#F5F7FA` | Background |
| `consumer-surface` | `#FFFFFF` | Card surfaces |
| `consumer-text` | `#1A2332` | Primary text |
| `consumer-muted` | `#6B7A8D` | Secondary text |
| `consumer-guardian` | `#0B6E7A` | Teal accent (trust signal) |

### Authority Theme (Dark, Data-Dense, Command Center)

| Token | Value | Purpose |
| --- | --- | --- |
| `authority-bg` | `#0E1522` | Dark background |
| `authority-surface` | `#18212F` | Card surfaces |
| `authority-cyan` | `#22B8CF` | Primary accent |
| `authority-amber` | `#E0A020` | Warning accent |
| `authority-red` | `#FF4D4D` | Alert accent |

### Verdict Colors (Color-Blind Safe)

| Token | Value | Purpose |
| --- | --- | --- |
| `verdict-safe` | `#1B8A5A` | Safe verdict |
| `verdict-suspicious` | `#C77A0A` | Suspicious verdict |
| `verdict-danger` | `#D12E2E` | Scam verdict |

### Interrupt Color

| Token | Value | Purpose |
| --- | --- | --- |
| `interrupt` | `#C4161C` | Full-bleed takeover screen |

### Accessibility

- `prefers-reduced-motion` overrides in `index.css` to scale down animations.
- Visible keyboard focus indicators (`:focus-visible`).
- Dual icon + text indicators for color-blind accessibility.

---

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend HTTP API base URL |
| `VITE_WS_BASE_URL` | `ws://localhost:8000` | Backend WebSocket base URL |

These are baked in at build time (Vite). Override with `--build-arg` in Docker.

---

## Setup

### Prerequisites

- **Node.js 20+**

### Install & Run

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

The dev server proxies API requests to the backend at `http://localhost:8000` by default.

---

## Scripts

| Script | Command | Description |
| --- | --- | --- |
| **Dev server** | `npm run dev` | Start Vite dev server on port 5173 |
| **Build** | `npm run build` | TypeScript check + Vite production build |
| **Preview** | `npm run preview` | Serve the production build locally |
| **Type check** | `npm run typecheck` | Run TypeScript compiler without emitting |
| **Translate guide** | `node scripts/translate_guide.mjs` | Generate guide locale files via local Ollama |

---

## Docker

Multi-stage build: Vite compiles the SPA, then Nginx Alpine serves the static files.

```bash
# Build
docker build -t kavach-frontend \
  --build-arg VITE_API_BASE_URL=http://your-backend:8000 \
  --build-arg VITE_WS_BASE_URL=ws://your-backend:8000 \
  .

# Run
docker run -p 80:80 kavach-frontend
```

The Nginx config includes SPA fallback routing so all client-side routes resolve to
`index.html`.
