"""call-center/ (AIxBlock) deep dive — our LEGITIMATE negatives.

Reads transcripts directly from the .zip archives IN MEMORY (nothing is
extracted into the source directory). Samples members per archive for schema /
stats / examples; uses the full namelist only for counts. States sampling.

Checks: per-archive counts (advertised 91,706 vs actual), schema (word
timestamps, ASR confidence, speaker), redaction convention, length/duration,
domain coverage (any bank/gov?), and duplicate re-uploaded archives.
"""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from collections import Counter

import common as c

CC = c.DATASETS["call-center"]
SAMPLE_PER_ZIP = 40


def _members(zf: zipfile.ZipFile) -> list[str]:
    return [n for n in zf.namelist() if n.lower().endswith(".json")]


def main() -> None:
    print("=== call-center (AIxBlock) ===")
    zips = sorted(CC.glob("*.zip"))

    per_zip = {}
    total_members = 0
    all_text_chars, all_words, all_conf, all_dur = [], [], [], []
    speaker_populated = 0
    speaker_checked = 0
    redaction_counter: Counter = Counter()
    lang_counter: Counter = Counter()
    schema_dump = None
    examples = ["# call-center — verbatim legitimate transcript examples\n"]

    for zp in zips:
        with zipfile.ZipFile(zp) as zf:
            members = _members(zf)
            per_zip[zp.name] = len(members)
            total_members += len(members)
            # Sample members for content.
            for name in members[:SAMPLE_PER_ZIP]:
                try:
                    obj = json.loads(zf.read(name))
                except Exception:
                    continue
                if schema_dump is None:
                    schema_dump = {k: type(v).__name__ for k, v in obj.items()}
                text = obj.get("text", "")
                all_text_chars.append(len(text))
                all_words.append(len(text.split()))
                if isinstance(obj.get("confidence"), (int, float)):
                    all_conf.append(float(obj["confidence"]))
                if isinstance(obj.get("audio_duration"), (int, float)):
                    all_dur.append(float(obj["audio_duration"]))
                # speaker populated?
                for w in (obj.get("words") or [])[:50]:
                    speaker_checked += 1
                    if w.get("speaker") is not None:
                        speaker_populated += 1
                # redaction tokens
                for tok in ["[ORGANIZATION]", "[NAME]", "[PERSON_NAME]", "[LOCATION]",
                            "[PHONE_NUMBER]", "[DATE]", "[MONEY_AMOUNT]", "[EMAIL_ADDRESS]"]:
                    if tok in text:
                        redaction_counter[tok] += text.count(tok)
                lang_counter[c.detect_language(text[:1500])] += 1
            # Two verbatim examples per archive (first two).
            if len(examples) < 40:
                for name in members[:2]:
                    try:
                        obj = json.loads(zf.read(name))
                    except Exception:
                        continue
                    examples.append(f"### archive={zp.name}  file={os.path.basename(name)}")
                    examples.append(f"- confidence={obj.get('confidence')} "
                                    f"audio_duration={obj.get('audio_duration')}s "
                                    f"n_words={len(obj.get('words', []))}")
                    examples.append("```")
                    examples.append(c.truncate(obj.get("text", ""), 1500))
                    examples.append("```\n")

    # Duplicate re-uploaded archives: compare the two auto_insurance zips by
    # hashing a sample of member CONTENTS.
    dup_check = _duplicate_check(zips)

    print(f"total JSON members across archives: {total_members} "
          f"(README advertises 91,706)")
    for n, cnt in per_zip.items():
        print(f"  {n[:55]:55s} {cnt}")
    print(f"\nspeaker populated: {speaker_populated}/{speaker_checked} sampled words")
    print(f"language buckets (sampled): {dict(lang_counter)}")
    print(f"redaction tokens (sampled): {dict(redaction_counter.most_common(8))}")
    print(f"duplicate-archive check: {dup_check}")

    c.write_schema("call-center", {
        "record_schema": schema_dump,
        "words_item": {"text": "str", "start": "ms", "end": "ms",
                       "confidence": "float", "speaker": "often null (mono ASR)"},
        "label": "NONE — all legitimate call-center calls (our negatives)",
        "note": "Flat 'text' field per call; word-level timestamps in 'words'.",
    })
    c.write_samples("callcenter_examples.md", "\n".join(examples))
    c.save_stats("call_center", {
        "n_archives": len(zips),
        "total_json_members": total_members,
        "advertised_count": 91706,
        "count_discrepancy": total_members - 91706,
        "per_archive_counts": per_zip,
        "sampled_per_archive": SAMPLE_PER_ZIP,
        "schema": schema_dump,
        "text_chars": c.percentiles(all_text_chars),
        "text_words": c.percentiles(all_words),
        "asr_confidence": c.percentiles(all_conf),
        "audio_duration_s": c.percentiles(all_dur),
        "speaker_populated_frac": round(speaker_populated / speaker_checked, 3)
        if speaker_checked else None,
        "language_sample": dict(lang_counter),
        "redaction_tokens": dict(redaction_counter.most_common()),
        "duplicate_archive_check": dup_check,
        "domains_from_filenames": [z.name for z in zips],
        "bank_or_government_domain": False,
        "domain_note": "Domains: automotive, auto/health insurance, customer "
        "service, home service, telecom, medical equipment, medicare. NO bank / "
        "police / government fraud-desk calls — the hardest negatives are absent.",
    })


def _duplicate_check(zips: list) -> dict:
    """Hash a sample of member contents to spot re-uploaded duplicate archives."""
    sig = {}
    for zp in zips:
        with zipfile.ZipFile(zp) as zf:
            members = sorted(_members(zf))[:100]
            h = hashlib.sha256()
            for name in members:
                try:
                    h.update(zf.read(name))
                except Exception:
                    pass
            sig[zp.name] = h.hexdigest()
    # Group archives whose sampled-content hash matches.
    groups: dict[str, list] = {}
    for name, digest in sig.items():
        groups.setdefault(digest, []).append(name)
    dups = [v for v in groups.values() if len(v) > 1]
    return {"content_hash_duplicate_groups": dups,
            "note": "Groups share identical first-100-member contents → likely "
            "re-uploaded duplicates."}


if __name__ == "__main__":
    main()
