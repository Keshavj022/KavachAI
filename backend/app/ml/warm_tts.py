"""Pre-generate Ramesh's common lines as cached TTS clips (build-time helper).

Run once after installing Indic Parler-TTS and downloading the model:

    python -m app.ml.warm_tts

It synthesizes the greeting and the stall toolkit for each supported language
into ``ml/tts_models/cache/precached/<lang>_<stall_type>.wav``. At runtime, if
the live model is slow or unavailable, ``tts_service.synthesize`` plays these
instantly. This is purely for demo reliability — the app runs (text-only) even
if this is never executed.
"""

from __future__ import annotations

from app.services import persona
from app.services.tts_service import PRECACHED_DIR, _ParlerTTS


def main() -> None:
    # Load synchronously here (this is an offline build script, so blocking is
    # fine and required — the runtime loader is non-blocking).
    try:
        tts = _ParlerTTS()
    except Exception as exc:
        print(f"Indic Parler-TTS could not load ({exc}). Install with:")
        print("  pip install git+https://github.com/huggingface/parler-tts.git")
        print("Then re-run this script to pre-cache clips.")
        return

    languages = ["hi", "en"]  # extend as needed
    count = 0
    for lang in languages:
        # These are all Ramesh (agent) lines, so use the agent description.
        desc = persona.parler_description("agent", lang)
        # Greeting.
        _write(tts, lang, "greeting", persona.greeting(lang), desc)
        count += 1
        # Stall toolkit.
        for stall_type in persona.STALL_TOOLKIT:
            line = persona.stall_line(stall_type, lang)
            _write(tts, lang, stall_type, line, desc)
            count += 1
        # Wrap-up line.
        _write(tts, lang, "wrap_up", persona.WRAP_UP_LINES.get(lang, ""), desc)
        count += 1
    print(f"Pre-cached {count} clips into {PRECACHED_DIR}")


def _write(tts, lang: str, stall_type: str, text: str, desc: str) -> None:
    if not text:
        return
    try:
        data = tts.synthesize(text, desc)
        (PRECACHED_DIR / f"{lang}_{stall_type}.wav").write_bytes(data)
        print(f"  {lang}/{stall_type}: {text[:40]}")
    except Exception as exc:
        print(f"  failed {lang}/{stall_type}: {exc}")


if __name__ == "__main__":
    main()
