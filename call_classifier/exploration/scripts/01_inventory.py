"""Inventory: recursive file listing, sizes, encodings, ICFD checksum verify.

Read-only. Writes stats['inventory'].
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

import common as c


def _dir_inventory(root: Path) -> dict:
    files = [p for p in root.rglob("*") if p.is_file() and p.name != ".DS_Store"]
    ext_counts: Counter[str] = Counter()
    total_bytes = 0
    hf_cache = 0
    for p in files:
        ext_counts[p.suffix.lower() or "(none)"] += 1
        sz = p.stat().st_size
        total_bytes += sz
        if ".cache/huggingface" in str(p):
            hf_cache += 1
    return {
        "n_files": len(files),
        "total_mb": round(total_bytes / 1e6, 2),
        "extensions": dict(ext_counts.most_common()),
        "hf_cache_files": hf_cache,
        "note": "'.cache/huggingface' files are HuggingFace download-cache "
        "artifacts (.lock/.metadata), not dataset content.",
    }


def _detect_encoding(path: Path) -> str:
    """Cheap encoding probe for text files."""
    raw = path.read_bytes()[:200_000]
    for enc in ("utf-8", "utf-8-sig", "latin-1", "windows-1252"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "unknown/binary"


def _verify_icfd_checksums(icfd: Path) -> dict:
    checks = icfd / "checksums.sha256"
    if not checks.exists():
        return {"available": False}
    entries = []
    for line in checks.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, rel = line.partition("  ")
        entries.append((digest, rel.strip()))

    passed = failed = missing = 0
    failures = []
    for digest, rel in entries:
        fp = icfd / rel
        if not fp.exists():
            missing += 1
            failures.append({"file": rel, "status": "missing"})
            continue
        h = hashlib.sha256()
        with open(fp, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        if h.hexdigest() == digest:
            passed += 1
        else:
            failed += 1
            failures.append({"file": rel, "status": "hash_mismatch"})
    return {
        "available": True,
        "total": len(entries),
        "passed": passed,
        "failed": failed,
        "missing": missing,
        "failures": failures[:20],
    }


def main() -> None:
    print("=== Inventory ===")
    inv: dict = {}
    for name, path in c.DATASETS.items():
        if not path.exists():
            inv[name] = {"error": "directory not found"}
            continue
        d = _dir_inventory(path)
        # Encoding probe for the small text files.
        text_files = [
            p for p in path.rglob("*")
            if p.is_file() and p.suffix.lower() in {".csv", ".md", ".json", ".jsonl"}
            and ".cache/huggingface" not in str(p)
        ]
        d["encodings"] = {
            str(p.relative_to(path)): _detect_encoding(p) for p in text_files[:20]
        }
        inv[name] = d
        print(f"  {name}: {d['n_files']} files, {d['total_mb']} MB, "
              f"ext={d['extensions']}")

    print("\n  verifying ICFD checksums (this reads every listed file)...")
    inv["icfd_checksums"] = _verify_icfd_checksums(c.DATASETS["icfd"])
    ck = inv["icfd_checksums"]
    if ck.get("available"):
        print(f"  checksums: {ck['passed']}/{ck['total']} passed, "
              f"{ck['failed']} failed, {ck['missing']} missing")

    c.save_stats("inventory", inv)


if __name__ == "__main__":
    main()
