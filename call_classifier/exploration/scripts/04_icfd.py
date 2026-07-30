"""ICFD-31k deep dive: source conversations + streaming chunks.

Answers:
  * label per split (final_verdict), split-size verification vs the card,
  * speaker attribution + multi-turn structure,
  * the stage-label question (chunk_level_analysis / verdict_at_chunk / rationale),
  * streaming chunks: CUMULATIVE vs incremental, chunks/conversation, cadence,
    per-chunk labels, and lead-time feasibility — with a worked example.

Reads ALL source conversations (streamed, ~31k) but only a SAMPLE of streaming
parquet shards (they total ~1.11M rows) — sampling is stated in the output.
Read-only.
"""

from __future__ import annotations

import glob
import io
import json
from collections import Counter, defaultdict

import pyarrow.parquet as pq
import zstandard as zstd

import common as c

ICFD = c.DATASETS["icfd"]
SRC_GLOB = str(ICFD / "source_conversations" / "*.jsonl.zst")
CHUNK_GLOB = str(ICFD / "streaming_chunks" / "*.parquet")


def _iter_jsonl_zst(path: str):
    with open(path, "rb") as fh:
        reader = zstd.ZstdDecompressor().stream_reader(fh)
        text = io.TextIOWrapper(reader, encoding="utf-8")
        for line in text:
            line = line.strip()
            if line:
                yield json.loads(line)


def analyze_sources() -> tuple[dict, list]:
    """Stream every source conversation; aggregate stats; keep a few examples."""
    per_split_verdict = defaultdict(Counter)
    per_split_case = defaultdict(Counter)
    per_split_domain = defaultdict(Counter)
    scam_outcome = Counter()
    langs = Counter()
    turns_by_verdict = defaultdict(list)
    chars_by_verdict = defaultdict(list)
    n_chunkanalysis = []
    verdict_transition_frac = []  # fraction of chunk_analysis that is YES
    examples = []
    keys_seen: Counter = Counter()
    total = 0

    for path in sorted(glob.glob(SRC_GLOB)):
        split = path.split("/")[-1].split("-")[0]
        for rec in _iter_jsonl_zst(path):
            total += 1
            keys_seen.update(rec.keys())
            verdict = rec.get("final_verdict", "?")
            per_split_verdict[split][verdict] += 1
            per_split_case[split][rec.get("scenario", {}).get("case_type",
                                  rec.get("case_type", "?"))] += 1
            dom = rec.get("release_metadata", {}).get("domain", "?")
            per_split_domain[split][dom] += 1
            scam_outcome[rec.get("scam_outcome", "?")] += 1

            transcript = rec.get("transcript", [])
            n_turns = len(transcript)
            full_text = " ".join(t.get("text", "") for t in transcript)
            turns_by_verdict[verdict].append(n_turns)
            chars_by_verdict[verdict].append(len(full_text))
            if total % 500 == 0:  # language on a sample (langdetect is slow)
                langs[c.detect_language(full_text[:1500])] += 1

            cla = rec.get("chunk_level_analysis", [])
            n_chunkanalysis.append(len(cla))
            if cla:
                yes = sum(1 for x in cla if str(x.get("verdict_at_chunk", "")).upper() == "YES")
                verdict_transition_frac.append(yes / len(cla))

            if len(examples) < 6 and split in {"train", "cross_domain"}:
                examples.append(rec)

    stats = {
        "total_source_records": total,
        "top_level_keys": dict(keys_seen),
        "per_split_verdict": {k: dict(v) for k, v in per_split_verdict.items()},
        "per_split_counts": {k: sum(v.values()) for k, v in per_split_verdict.items()},
        "per_split_case_type": {k: dict(v) for k, v in per_split_case.items()},
        "domains": {k: dict(v) for k, v in per_split_domain.items()},
        "scam_outcome": dict(scam_outcome),
        "language_sample": dict(langs),
        "turns": {v: c.percentiles(l) for v, l in turns_by_verdict.items()},
        "chars": {v: c.percentiles(l) for v, l in chars_by_verdict.items()},
        "chunk_level_analysis_per_conv": c.percentiles(n_chunkanalysis),
        "mean_frac_chunkanalysis_YES": round(
            sum(verdict_transition_frac) / len(verdict_transition_frac), 3
        ) if verdict_transition_frac else None,
    }
    return stats, examples


def analyze_streaming(sample_shards: int = 2) -> dict:
    """Sample streaming shards; confirm cumulative vs incremental; cadence."""
    shards = sorted(glob.glob(CHUNK_GLOB))
    # Sample a couple of train shards for structure + one of each other split.
    picks = [s for s in shards if "/train-" in s][:sample_shards]
    for other in ("validation-", "test-", "cross_domain-"):
        got = next((s for s in shards if f"/{other}" in s), None)
        if got:
            picks.append(got)

    columns_seen = None
    chunks_per_conv = []
    timestamps_sample = []
    cumulative_confirmed = None
    cadence_deltas = Counter()
    per_chunk_label_is_final = None
    walkthrough = None

    for path in picks:
        t = pq.read_table(path)
        if columns_seen is None:
            columns_seen = t.column_names
        df = t.to_pandas()
        # Group by conversation.
        for uid, grp in df.groupby("conversation_uid"):
            grp = grp.sort_values("chunk_timestamp")
            chunks_per_conv.append(len(grp))
            ts = grp["chunk_timestamp"].tolist()
            timestamps_sample.extend(ts[:10])
            for a, b in zip(ts, ts[1:]):
                cadence_deltas[int(b - a)] += 1
            # Cumulative check: is each chunk text a prefix-superset of the previous?
            texts = grp["cumulative_text"].tolist()
            if cumulative_confirmed is None and len(texts) >= 3:
                mono = all(len(texts[i]) >= len(texts[i - 1]) for i in range(1, len(texts)))
                prefix = all(texts[i].startswith(texts[i - 1][: min(80, len(texts[i - 1]))])
                             for i in range(1, len(texts)))
                cumulative_confirmed = {"length_monotonic": mono, "prefix_growing": prefix}
                # Per-chunk label: does final_verdict vary within a conversation?
                per_chunk_label_is_final = grp["final_verdict"].nunique() == 1
                walkthrough = (uid, grp)

    stats = {
        "sampled_shards": [p.split("/")[-1] for p in picks],
        "columns": columns_seen,
        "chunks_per_conversation": c.percentiles(chunks_per_conv),
        "chunk_timestamp_examples": sorted(set(timestamps_sample))[:20],
        "cadence_delta_seconds_top": dict(cadence_deltas.most_common(6)),
        "cumulative_check": cumulative_confirmed,
        "final_verdict_constant_within_conversation": per_chunk_label_is_final,
        "note": "Streaming stats are from sampled shards (stated above), not all "
        "1.11M chunks. 'cumulative_text' column name + the checks confirm chunks "
        "are CUMULATIVE (each contains all text so far).",
    }
    return stats, walkthrough


def write_examples(src_examples: list) -> None:
    out = ["# ICFD — full conversation examples\n"]
    for rec in src_examples[:5]:
        rm = rec.get("release_metadata", {})
        out.append(f"### session_id={rec.get('session_id')} | split={rm.get('split')} "
                   f"| domain={rm.get('domain')} | final_verdict={rec.get('final_verdict')} "
                   f"| case_type={rec.get('scenario', {}).get('case_type', rec.get('case_type'))}")
        out.append(f"- scam_outcome: {rec.get('scam_outcome')}")
        out.append(f"- agent_persona: {c.truncate(rec.get('agent_persona',''),200)}")
        out.append(f"- multimodal_analysis: {json.dumps(rec.get('multimodal_analysis',{}))}")
        out.append("- transcript:")
        out.append("```")
        turns = "\n".join(f"{t.get('speaker')}: {t.get('text')}"
                          for t in rec.get("transcript", []))
        out.append(c.truncate(turns, 2000))
        out.append("```\n")
    c.write_samples("icfd_examples.md", "\n".join(out))


def write_walkthrough(src_examples: list, walkthrough) -> None:
    """One full conversation + its consecutive cumulative chunks side by side."""
    out = ["# ICFD streaming walkthrough — cumulative-chunk behaviour\n"]
    if walkthrough is None:
        out.append("_No walkthrough captured._")
        c.write_samples("icfd_streaming_walkthrough.md", "\n".join(out))
        return
    uid, grp = walkthrough
    grp = grp.sort_values("chunk_timestamp")
    out.append(f"Conversation UID: `{uid}`  |  final_verdict={grp['final_verdict'].iloc[0]}")
    out.append(f"Total chunks: {len(grp)}  |  timestamps(s): "
               f"{grp['chunk_timestamp'].tolist()[:12]} ...\n")

    out.append("## Full cumulative transcript at the LAST chunk\n```")
    out.append(c.truncate(grp["cumulative_text"].iloc[-1], 2500))
    out.append("```\n")

    out.append("## First 5 consecutive chunks (note text GROWS = cumulative)\n")
    for _, r in grp.head(5).iterrows():
        out.append(f"### chunk @ {r['chunk_timestamp']}s  "
                   f"(len={len(r['cumulative_text'])} chars)")
        out.append(f"- rationale: {c.truncate(str(r['slow_thinking_rationale']), 300)}")
        out.append("```")
        out.append(c.truncate(r["cumulative_text"], 900))
        out.append("```\n")

    # Also show the SOURCE chunk_level_analysis (per-timestamp verdict) for a rec.
    rec = next((r for r in src_examples if r.get("chunk_level_analysis")), None)
    if rec:
        out.append("## SOURCE chunk_level_analysis — per-timestamp verdict + rationale\n")
        out.append(f"(session_id={rec.get('session_id')}, final_verdict={rec.get('final_verdict')})\n")
        out.append("| timestamp | verdict_at_chunk | rationale |")
        out.append("| --- | --- | --- |")
        for x in rec["chunk_level_analysis"][:14]:
            out.append(f"| {x.get('timestamp')} | {x.get('verdict_at_chunk')} | "
                       f"{c.truncate(str(x.get('rationale_at_chunk','')), 90)} |")
    c.write_samples("icfd_streaming_walkthrough.md", "\n".join(out))


def plots(src_stats: dict) -> None:
    import matplotlib.pyplot as plt

    # Turns per conversation by verdict.
    fig, ax = plt.subplots(figsize=(7, 4.5))
    verds = [v for v in src_stats["turns"] if src_stats["turns"][v]]
    meds = [src_stats["turns"][v]["median"] for v in verds]
    ax.bar(verds, meds, color=["#C62828" if v == "YES" else "#2E7D32" for v in verds])
    ax.set_ylabel("median turns/conversation")
    ax.set_title("ICFD: median turns per conversation by final_verdict",
                 fontsize=11, fontweight="bold")
    c.savefig(fig, "icfd_turns_by_verdict.png")


def main() -> None:
    print("=== ICFD-31k ===")
    print("reading all source conversations (streamed)...")
    src_stats, examples = analyze_sources()
    print(f"  total source records: {src_stats['total_source_records']}")
    print(f"  per-split counts: {src_stats['per_split_counts']}")
    print(f"  per-split verdict: {src_stats['per_split_verdict']}")
    print(f"  scam_outcome: {src_stats['scam_outcome']}")
    print(f"  language sample: {src_stats['language_sample']}")

    print("\nanalyzing streaming chunks (sampled shards)...")
    stream_stats, walkthrough = analyze_streaming()
    print(f"  columns: {stream_stats['columns']}")
    print(f"  cumulative check: {stream_stats['cumulative_check']}")
    print(f"  chunks/conversation: {stream_stats['chunks_per_conversation']}")
    print(f"  cadence deltas (s): {stream_stats['cadence_delta_seconds_top']}")
    print(f"  final_verdict constant within conversation: "
          f"{stream_stats['final_verdict_constant_within_conversation']}")

    write_examples(examples)
    write_walkthrough(examples, walkthrough)
    plots(src_stats)

    c.write_schema("icfd", {
        "source_record_keys": src_stats["top_level_keys"],
        "streaming_columns": stream_stats["columns"],
        "transcript_turn_shape": {"speaker": "Agent|Customer", "text": "str"},
        "stage_or_phase_field": "NONE explicit; chunk_level_analysis gives "
        "per-timestamp verdict_at_chunk (YES/NO) + rationale_at_chunk (free text)",
    })
    c.save_stats("icfd", {"source": src_stats, "streaming": stream_stats})


if __name__ == "__main__":
    main()
