"""Kavach AI — FastAPI application entrypoint.

Wires CORS, rate limiting, routers and the live-call websocket. Routers are
included defensively: a module that fails to import (e.g. an optional ML
dependency missing during early setup) logs a warning instead of taking the
whole app down, so the core auth flow always runs on a fresh clone.
"""

import importlib
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db
from app.rate_limit import limiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kavach")

app = FastAPI(
    title="Kavach AI",
    description="Digital Arrest & Fraud Shield — detection, reporting and fraud intelligence.",
    version="0.1.0",
)

# --- Rate limiting ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS: explicit origins only, never "*" in production. ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    """Create tables on startup so a fresh clone runs without a migration step."""
    init_db()
    logger.info("Database initialised. Kavach AI backend ready.")
    # Warm the decoy pipeline in the background (non-blocking) so the first live
    # call is not slowed by one-time model loads: the TTS model, the on-device
    # detector, and the local LLM (Ollama). Each is best-effort and never blocks
    # startup or the request path.
    import threading

    def _warm() -> None:
        try:
            from app.config import settings
            from app.services import tts_service
            if (settings.tts_engine or "parler").lower() == "parler":
                # Load + warm the model ON the dedicated TTS thread (the same
                # thread every synthesis runs on), and pay the first-generate MPS
                # kernel compilation here so real calls are fast.
                tts_service.tts_pool.submit(tts_service.warm_parler_blocking).result()
            else:
                tts_service.start_loading()
        except Exception:
            pass
        try:
            from app.services.call_detector import detect
            detect("warmup")  # loads the trained call models
        except Exception:
            pass
        try:
            import httpx

            from app.config import settings
            from app.services import text_llm
            if text_llm.provider() == "ollama":
                # Only worth warming a LOCAL model — Groq is stateless cloud.
                httpx.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={"model": settings.ollama_model, "prompt": "hi",
                          "stream": False, "keep_alive": "30m",
                          "options": {"num_predict": 1,
                                      "num_gpu": settings.ollama_num_gpu}},
                    timeout=60.0,
                )  # loads the LLM (on CPU by default) and holds it warm
        except Exception:
            pass

    threading.Thread(target=_warm, name="decoy-warm", daemon=True).start()


@app.get("/api/health", tags=["health"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "service": "kavach"}


# --- Routers ---
# Each entry is (module path, attribute). Included defensively so a single
# broken optional module cannot break the whole surface during development.
_ROUTER_MODULES = [
    "app.api.routes.auth",
    "app.api.routes.detection",
    "app.api.routes.call",
    "app.api.routes.reports",
    "app.api.routes.contacts",
    "app.api.routes.graph",
    "app.api.routes.evidence",
    "app.api.routes.ws",
    "app.api.routes.decoy",
    "app.api.routes.guide",
]

for _module_path in _ROUTER_MODULES:
    try:
        _mod = importlib.import_module(_module_path)
        app.include_router(_mod.router)
        logger.info("Mounted router: %s", _module_path)
    except ModuleNotFoundError:
        # Router not built yet (phased development) — skip quietly.
        logger.info("Router not present yet, skipping: %s", _module_path)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to mount router %s: %s", _module_path, exc)
