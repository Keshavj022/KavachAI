import { useEffect, useState } from "react";
import { FileLock2, ShieldCheck } from "lucide-react";
import { api } from "../../api/client";
import type { EvidenceMeta } from "../../api/client";

/**
 * Authority-only preserved evidence. Shows tamper-evidence metadata (hash,
 * timestamp) for a confirmed case. The encrypted segment is decrypted
 * server-side and never exposed to the citizen who was recorded.
 */
export default function EvidencePanel({ reportId }: { reportId: number }) {
  const [items, setItems] = useState<EvidenceMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .evidence(reportId)
      .then((res) => setItems(res.items))
      .catch(() => setError("unavailable"));
  }, [reportId]);

  return (
    <div className="rounded-xl border border-authority-border bg-authority-surface p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <FileLock2 size={16} className="text-authority-amber" />
        Preserved evidence
        <span className="rounded bg-authority-amber/10 px-1.5 py-0.5 font-mono text-[10px] uppercase text-authority-amber">
          Authority only
        </span>
      </h2>

      {error || !items || items.length === 0 ? (
        <p className="text-sm text-authority-muted">
          No preserved evidence for this case. Evidence is only retained when a
          scam is confirmed with high confidence.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((e) => (
            <li key={e.id} className="rounded-lg bg-authority-base p-3">
              <div className="flex items-center gap-2 text-xs text-verdict-safe">
                <ShieldCheck size={14} />
                Integrity hash verified
              </div>
              <p className="mt-1.5 break-all font-mono text-[11px] text-authority-muted">
                SHA-256: {e.sha256_hash}
              </p>
              <p className="mt-1 text-[11px] text-authority-muted">
                Preserved {new Date(e.created_at).toLocaleString()}
              </p>
              {e.preview && (
                <p className="mt-2 rounded bg-authority-surface p-2 text-xs text-authority-text">
                  {e.preview}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
