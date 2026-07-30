"""Phase 3 — Stage annotation (BUILD TIME ONLY, never at inference).

Groq is used here as an OFFLINE ANNOTATOR to generate scam-arc stage labels for
ICFD scam conversations, because no dataset ships them. The trained arc tracker
learns from these labels; at runtime there is NO Groq call.

Output per conversation (strict): turn_stages (monotonic), money_demand_turn,
money_demand_timestamp (looked up from the source per-turn timestamps).

FIREWALL: train+val scam conversations are annotated for TRAINING
(``stage_labels/train_val.jsonl``); test scam conversations are annotated in a
separate pass (``stage_labels/test.jsonl``) used ONLY to score lead-time at
evaluation. youtube-scam is never annotated.

Resumable: results are cached per conversation; re-running extends coverage and
never re-annotates. If Groq is unreachable / no key, a transparent rule-based
fallback labels the conversation instead (recorded as ``source="fallback"``) so
the pipeline still completes — the report states which was used.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

load_dotenv(config.REPO_ROOT / ".env")  # GROQ_API_KEY (build-time only)
GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()

config.STAGE_LABELS_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """\
You label the scam-arc stage of each turn in a scam phone call transcript.
Stages, in strict escalation order:
- none: greeting/small talk, nothing suspicious yet.
- authority_claim: caller claims to be police, CBI, a bank, government, courier
  (FedEx), TRAI, tax/customs, or similar authority; references a parcel, SIM,
  Aadhaar, account, or case.
- accusation: alleges a crime / creates fear — money laundering, illegal parcel,
  drugs, account misuse, arrest warrant, FIR, non-bailable offence.
- isolation: demands secrecy or control — "do not tell anyone", "stay on the
  call", "do not disconnect", "this is confidential", "you are under arrest".
- money_demand: asks for money or its keys — transfer, RTGS/UPI, "safe/
  verification account", OTP, card number/CVV, gift card, crypto, a fee/deposit.

Rules:
- Stages are MONOTONIC: once a stage is reached the call does not regress.
- Return the FIRST turn index at which each reached stage begins.
- money_demand_turn is the first money-demand turn, or null if the call never
  demands money.

Return STRICT JSON only:
{"turn_stages": [{"turn_index": 0, "stage": "none"}, ...],
 "money_demand_turn": 11}
Include one entry per turn index you are given, using the stage in force at that
turn (carry the highest stage reached forward)."""


# --- Rule-based fallback ----------------------------------------------------
_CUES = {
    "authority_claim": ["police", "cbi", "officer", "department", "government",
                        "bank", "fedex", "courier", "trai", "customs", "tax",
                        "interpol", "agent", "calling from", "verification team"],
    "accusation": ["money laundering", "arrest", "warrant", "illegal", "drugs",
                   "parcel", "case has been", "fir", "misused", "suspicious",
                   "fraudulent", "non-bailable", "complaint"],
    "isolation": ["do not tell", "don't tell", "do not disconnect",
                  "don't disconnect", "stay on", "confidential", "do not hang",
                  "don't hang", "under arrest", "surveillance", "nobody"],
    "money_demand": ["transfer", "rtgs", "neft", "upi", "safe account",
                     "verification account", "otp", "card number", "cvv",
                     "gift card", "bitcoin", "deposit", "pay the", "fee",
                     "security amount"],
}


def rule_annotate(turns: list[dict]) -> tuple[list[dict], int | None]:
    order = config.STAGE_ORDER
    current = "none"
    stages = []
    money_turn = None
    for i, t in enumerate(turns):
        text = (t.get("text") or "").lower()
        for stage in ("authority_claim", "accusation", "isolation", "money_demand"):
            if order[stage] > order[current] and any(c in text for c in _CUES[stage]):
                current = stage
                if stage == "money_demand" and money_turn is None:
                    money_turn = i
        stages.append({"turn_index": i, "stage": current})
    return stages, money_turn


# --- Groq annotator ---------------------------------------------------------
def groq_annotate(turns: list[dict], retries: int = 3) -> tuple[list, int | None] | None:
    numbered = "\n".join(f"[{i}] {t.get('speaker')}: {t.get('text')}"
                         for i, t in enumerate(turns))
    payload = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Turns:\n{numbered}"},
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"},
    }
    for attempt in range(retries):
        try:
            r = httpx.post(f"{config.GROQ_BASE_URL}/chat/completions",
                           headers={"Authorization": f"Bearer {GROQ_KEY}"},
                           json=payload, timeout=45)
            if r.status_code == 429:  # rate limited — back off
                time.sleep(2 ** attempt + 1)
                continue
            r.raise_for_status()
            data = json.loads(r.json()["choices"][0]["message"]["content"])
            return data.get("turn_stages", []), data.get("money_demand_turn")
        except Exception as exc:
            if attempt == retries - 1:
                print(f"    groq failed ({exc}); using fallback")
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def enforce_monotonic(turn_stages: list[dict], n_turns: int) -> list[str]:
    """Return a per-turn stage list, forced monotonic and length n_turns."""
    order = config.STAGE_ORDER
    by_turn = {}
    for e in turn_stages:
        try:
            by_turn[int(e["turn_index"])] = e.get("stage", "none")
        except (TypeError, ValueError, KeyError):
            continue
    out = []
    current = "none"
    for i in range(n_turns):
        stage = by_turn.get(i, current)
        if stage not in order:
            stage = current
        if order[stage] < order[current]:
            stage = current  # monotonic: never regress
        current = stage
        out.append(current)
    return out


def flip_timestamp(chunk_analysis: list) -> float | None:
    """First timestamp where ICFD's chunk_level_analysis flips NO→YES."""
    for x in chunk_analysis:
        if str(x.get("verdict_at_chunk", "")).upper() == "YES":
            return x.get("timestamp")
    return None


def stage_first_ts(stages: list[str], turns: list[dict], stage: str) -> float | None:
    for i, s in enumerate(stages):
        if s == stage:
            return turns[i].get("ts")
    return None


def annotate_split(df: pd.DataFrame, splits: list[str], out_path: Path, limit: int,
                   pass_name: str) -> dict:
    done = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                done.add(json.loads(line)["conversation_id"])
    pool = df[(df.source_dataset == "icfd") & (df.label == 1) & (df.split.isin(splits))]
    pool = pool.sort_values("conversation_id").head(limit)

    used = {"groq": 0, "fallback": 0}
    flip_hits = flip_total = 0
    with open(out_path, "a") as fh:
        for _, row in pool.iterrows():
            cid = row["conversation_id"]
            if cid in done:
                continue
            turns = json.loads(row["turns_json"])
            res = groq_annotate(turns) if GROQ_KEY else None
            if res is None:
                turn_stages_raw, money_turn = rule_annotate(turns)
                source = "fallback"
            else:
                turn_stages_raw, money_turn = res
                source = "groq"
            used[source] += 1

            stages = enforce_monotonic(turn_stages_raw, len(turns))
            if money_turn is None or not (0 <= int(money_turn) < len(turns)):
                money_turn = next((i for i, s in enumerate(stages)
                                   if s == "money_demand"), None)
            money_ts = turns[int(money_turn)].get("ts") if money_turn is not None else None

            # Validation against ICFD chunk_level_analysis NO->YES flip.
            flip = flip_timestamp(json.loads(row["chunk_analysis_json"]))
            acc_ts = stage_first_ts(stages, turns, "accusation")
            iso_ts = stage_first_ts(stages, turns, "isolation")
            near_flip = None
            if flip is not None:
                det = iso_ts if iso_ts is not None else acc_ts
                if det is not None:
                    near_flip = abs(det - flip) <= 30  # within ~30s
                    flip_total += 1
                    flip_hits += int(near_flip)

            rec = {
                "conversation_id": cid, "split": row["split"], "source": source,
                "n_turns": len(turns), "stages": stages,
                "money_demand_turn": None if money_turn is None else int(money_turn),
                "money_demand_timestamp": money_ts,
                "authority_ts": stage_first_ts(stages, turns, "authority_claim"),
                "accusation_ts": acc_ts, "isolation_ts": iso_ts,
                "flip_timestamp": flip, "detection_near_flip": near_flip,
            }
            fh.write(json.dumps(rec) + "\n")
            fh.flush()

    agree = round(flip_hits / flip_total, 3) if flip_total else None
    print(f"  [{pass_name}] annotated {sum(used.values())} new "
          f"(groq={used['groq']}, fallback={used['fallback']}); "
          f"flip-agreement={agree} (n={flip_total})")
    return {"pass": pass_name, "counts": used, "flip_agreement": agree,
            "flip_n": flip_total, "output": str(out_path.name)}


def save_samples(out_path: Path, n: int = 30) -> None:
    if not out_path.exists():
        return
    recs = [json.loads(l) for l in out_path.read_text().splitlines() if l.strip()][:n]
    df = pd.read_parquet(config.CORPUS_PARQUET)[["conversation_id", "turns_json"]]
    tmap = dict(zip(df.conversation_id, df.turns_json))
    lines = ["# Stage-annotation samples (for manual review)\n"]
    for r in recs:
        turns = json.loads(tmap.get(r["conversation_id"], "[]"))
        lines.append(f"### {r['conversation_id']} (source={r['source']}, "
                     f"money_demand_turn={r['money_demand_turn']}, "
                     f"flip@{r['flip_timestamp']}s, near_flip={r['detection_near_flip']})")
        for i, t in enumerate(turns):
            lines.append(f"  [{i}] ({r['stages'][i]}) {t.get('speaker')}: "
                         f"{(t.get('text') or '')[:140]}")
        lines.append("")
    (config.REPORTS / "stage_annotation_samples.md").write_text("\n".join(lines))
    print(f"  saved {n} annotation samples to reports/stage_annotation_samples.md")


def main() -> None:
    config.set_global_seed()
    print(f"=== Phase 3: stage annotation (annotator={'groq' if GROQ_KEY else 'RULE-FALLBACK (no key)'}) ===")
    df = pd.read_parquet(config.CORPUS_PARQUET)

    meta = {"annotator": "groq" if GROQ_KEY else "fallback", "passes": []}
    # Training labels — train + val scam (firewalled from test).
    meta["passes"].append(annotate_split(
        df, ["train", "val"], config.STAGE_LABELS_DIR / "train_val.jsonl",
        config.ANNOTATE_MAX_TRAIN_VAL, "train_val"))
    # Test labels — separate pass, used only for lead-time at eval.
    meta["passes"].append(annotate_split(
        df, ["test"], config.STAGE_LABELS_DIR / "test.jsonl",
        config.ANNOTATE_MAX_TEST, "test"))

    save_samples(config.STAGE_LABELS_DIR / "train_val.jsonl")
    with open(config.STAGE_LABELS_DIR / "annotation_meta.json", "w") as fh:
        json.dump(meta, fh, indent=2)
    print("  done.")


if __name__ == "__main__":
    main()
