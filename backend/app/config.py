"""Application configuration loaded from environment / .env.

All secrets and tunables come from environment variables. Nothing is
hardcoded. Missing optional values (Twilio, Ollama, evidence key) cause the
relevant feature to degrade gracefully rather than crash — see the services
that consume them.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    Values are read from the process environment, falling back to a local
    ``.env`` file at the repository root or backend directory.
    """

    # --- Auth ---
    jwt_secret: str = "change-me-long-random-string"
    jwt_expire_minutes: int = 120
    jwt_algorithm: str = "HS256"

    # --- Evidence encryption (Fernet key). If empty, a volatile key is
    #     generated at startup so the app still runs; preserved evidence
    #     then only survives for the current process, which is fine for a
    #     demo but must be set in production. ---
    evidence_key: str = ""

    # --- Database ---
    database_url: str = "sqlite:///./kavach.db"

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173"

    # --- LLM reasoning (Ollama, local) — used only for message-path
    #     explanations. The call path is fully local (trained models). ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    # Ollama GPU layers. On a single-GPU Mac the decoy's TTS (Parler) also needs
    # the GPU, and the two contend badly — running the LLM on CPU (0) frees the
    # GPU for TTS and cuts synthesis latency ~3x while the LLM stays fast enough.
    # Set higher on a machine with a dedicated, roomy GPU.
    ollama_num_gpu: int = 0

    # --- Text generation provider (the fraudster + decoy lines) --------------
    # "auto" uses Groq when GROQ_API_KEY is set (fast, cloud — frees the local GPU
    # entirely for TTS), else falls back to local Ollama. Force with "groq" or
    # "ollama". NOTE: Groq sends the transcript to the cloud, so the fully-local
    # privacy story requires "ollama".
    text_provider: str = "auto"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    # --- Trained on-device models (configurable dirs) ---
    # The call path runs a local trained classifier + arc tracker; the message
    # path runs the trained SMS SVM. Both fall back to rules if the artifacts
    # are absent. NOTE: Groq is NOT used at runtime — it is a BUILD-TIME-ONLY
    # dependency of call_classifier/src/03_annotate_stages.py (label generation
    # on public data). There is no network call in the runtime detection path.
    call_model_dir: str = ""  # default resolved in call_detector.py
    sms_model_dir: str = ""   # default resolved in classifier.py

    # --- Interrupt decision (deterministic, in code — not learned). Tunable. ---
    interrupt_threshold: float = 0.7

    # --- Twilio (optional) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # --- STT (faster-whisper, LOCAL). `medium` gives better Hindi/Hinglish
    #     quality; drop to `base`/`small` for a faster CPU demo. ---
    whisper_model_size: str = "medium"

    # --- Text-to-speech (decoy voice) ---------------------------------------
    # Engine: "parler" (ai4bharat/indic-parler-tts — the primary voice engine,
    # runs live on CPU/MPS) or "svara" (kenpath/svara-tts-v1, an Orpheus-style 3B
    # model whose real-time path needs a vLLM GPU; kept for the submitted build).
    tts_engine: str = "parler"
    svara_model: str = "kenpath/svara-tts-v1"
    svara_snac_model: str = "hubertsiuzdak/snac_24khz"
    # Backend for svara: "off" (default — skip live synthesis and serve only the
    # pre-generated cache clips; the safe local-demo path on a laptop), "vllm"
    # (real-time; the deployed GPU build sets this), "transformers" (portable but
    # slow — used mainly by the offline pre-gen script), or "auto" (vLLM if
    # importable, else transformers).
    svara_backend: str = "off"
    # Device override for the TTS models (""=auto: mps→cuda→cpu).
    tts_device: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        """Allowed CORS origins.

        Accepts a comma-separated ``FRONTEND_ORIGIN`` so multiple deployed
        frontends can be permitted without a wildcard.
        """
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def twilio_enabled(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_from_number
        )



@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
