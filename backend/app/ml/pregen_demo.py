"""Pre-generate the fixed demo voice clips into the TTS cache, once.

This renders every fixed demo line — each caller turn and each scripted Ramesh
reply, plus the greeting — ahead of time and writes them under the exact names
the live server looks up, so the demo plays smooth, in-sync, dual-voice audio
straight from disk with no synthesis on the hot path.

It uses whichever engine ``TTS_ENGINE`` selects:
  * ``parler`` (default) — Indic Parler-TTS, fast enough to render on CPU/MPS.
  * ``svara`` — the 3B model via its portable transformers backend (slow; a
    one-time step, downloads ~14 GB on first use).

Run once (``--force`` re-renders existing clips, e.g. after a voice change)::

    python -m app.ml.pregen_demo
    python -m app.ml.pregen_demo --force
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.config import settings
from app.services import persona, tts_service

_SCRIPTS_DIR = Path(__file__).resolve().parent / "demo_scripts"


def _lines_for_script(script: dict) -> list[tuple[str, str, str]]:
    """Return (role, language, text) tuples for every spoken line in a script."""
    lang = script.get("language", "hi")
    out: list[tuple[str, str, str]] = [("agent", lang, persona.greeting(lang))]
    for turn in script.get("turns", []):
        if turn.get("speaker") != "scammer":
            continue
        out.append(("scammer", lang, turn["text"]))
        if turn.get("agent_text"):
            out.append(("agent", lang, turn["agent_text"]))
    return out


def _render(role: str, language: str, text: str, force: bool) -> str:
    """Synthesize one line with the active engine; return a status word."""
    return tts_service.pregenerate(text, language, role, force=force)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-generate demo TTS clips.")
    parser.add_argument("--force", action="store_true", help="re-render existing clips")
    args = parser.parse_args()

    scripts = sorted(_SCRIPTS_DIR.glob("*.json"))
    if not scripts:
        print(f"No demo scripts found in {_SCRIPTS_DIR}")
        return

    # De-duplicate lines shared across scripts (e.g. the same-language greeting).
    seen: set[tuple[str, str, str]] = set()
    lines: list[tuple[str, str, str]] = []
    for path in scripts:
        for item in _lines_for_script(json.loads(path.read_text(encoding="utf-8"))):
            if item not in seen:
                seen.add(item)
                lines.append(item)

    engine = (settings.tts_engine or "parler").lower()
    print(f"Pre-generating {len(lines)} demo clips with engine='{engine}' "
          f"(force={args.force}). First run downloads the model — be patient.\n")
    counts = {"write": 0, "skip": 0, "fail": 0}
    for i, (role, language, text) in enumerate(lines, 1):
        t0 = time.time()
        status = _render(role, language, text, args.force)
        counts[status] += 1
        print(f"[{i}/{len(lines)}] {status:5s} {time.time() - t0:6.1f}s  "
              f"{role}/{language}: {text[:56]}…", flush=True)

    print(f"\nDone. written={counts['write']} skipped={counts['skip']} "
          f"failed={counts['fail']}")
    if counts["fail"]:
        print("Some clips failed — check the TTS model is installed and loadable "
              "on this machine. The demo still runs (those lines play text-timed).")


if __name__ == "__main__":
    main()
