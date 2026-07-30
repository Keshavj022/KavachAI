import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, ChevronDown, PhoneOff, ShieldX } from "lucide-react";
import { api, DecoyPackage } from "../api/client";
import IntelligencePackageCard from "./IntelligencePackageCard";

const CATEGORY_LABEL: Record<string, string> = {
  digital_arrest: "Digital Arrest",
  kyc_update: "KYC Fraud",
  investment: "Investment Scam",
  fake_delivery: "Fake Delivery",
  refund: "Refund Scam",
  loan: "Loan Scam",
  other: "Phone Scam",
};

/**
 * Shown after a decoy call ends with a scam verdict. Summarizes how long Ramesh
 * kept the scammer talking and everything they revealed, and offers the report
 * actions. A safe verdict shows a simple "connecting you" state instead.
 */
export default function ScamVerdictScreen({
  verdict,
  packageId,
  durationSeconds,
  onDismiss,
  onNewCall,
}: {
  verdict: "scam" | "safe";
  packageId: string | null;
  durationSeconds: number;
  onDismiss: () => void;
  onNewCall: () => void;
}) {
  const [pkg, setPkg] = useState<DecoyPackage | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<string | null>(null);

  useEffect(() => {
    if (verdict === "scam" && packageId) {
      api.getDecoyPackage(packageId).then(setPkg).catch(() => setPkg(null));
    }
  }, [verdict, packageId]);

  if (verdict === "safe") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
        <CheckCircle2 size={44} className="text-verdict-safe" />
        <h2 className="font-display text-xl font-bold text-consumer-ink">
          This appears to be a real call
        </h2>
        <p className="text-sm text-consumer-muted">
          Kavach did not detect a scam. In a live deployment it would connect you
          now.
        </p>
        <button
          onClick={onNewCall}
          className="mt-2 rounded-xl border border-consumer-accent/30 px-4 py-2 text-sm font-semibold text-consumer-accent"
        >
          Done
        </button>
      </div>
    );
  }

  const minutes = Math.max(1, Math.round(durationSeconds / 60));
  const category = pkg ? CATEGORY_LABEL[pkg.scam_type] ?? "Phone Scam" : "Phone Scam";

  async function submit(channel: string) {
    if (!packageId) return;
    setSubmitting(channel);
    try {
      const res = await api.submitDecoyPackage(packageId, channel);
      setSubmitted(res.submission_id);
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-verdict-danger px-5 pb-5 pt-6 text-white"
      >
        <div className="flex items-center gap-2">
          <ShieldX size={26} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-white/80">
              Scam confirmed
            </p>
            <h1 className="font-display text-2xl font-bold leading-tight">{category}</h1>
          </div>
        </div>
        <p className="mt-3 text-sm leading-snug text-white/95">
          Kavach kept them talking for {minutes} minute{minutes > 1 ? "s" : ""}.
          Here's what they revealed:
        </p>
      </motion.div>

      <div className="space-y-4 px-4 py-4">
        {pkg ? (
          <IntelligencePackageCard pkg={pkg} />
        ) : (
          <p className="text-sm text-consumer-muted">Building intelligence package…</p>
        )}

        {pkg && (
          <div className="rounded-2xl border border-gray-200 bg-white">
            <button
              onClick={() => setShowTranscript((s) => !s)}
              className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-consumer-ink"
            >
              Full transcript
              <ChevronDown
                size={16}
                className={`transition ${showTranscript ? "rotate-180" : ""}`}
              />
            </button>
            {showTranscript && (
              <pre className="max-h-56 overflow-y-auto whitespace-pre-wrap border-t border-gray-100 px-4 py-3 text-xs leading-relaxed text-consumer-muted">
                {pkg.transcript}
              </pre>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="space-y-2 pb-4">
          {submitted ? (
            <div className="rounded-xl bg-verdict-safe/10 px-4 py-3 text-center text-sm font-medium text-verdict-safe">
              Report submitted · reference {submitted}
            </div>
          ) : (
            <>
              <button
                onClick={() => submit("1930")}
                disabled={!packageId || submitting !== null}
                className="w-full rounded-xl bg-consumer-accent py-3 font-semibold text-white disabled:opacity-60"
              >
                {submitting === "1930" ? "Submitting…" : "Report to 1930"}
              </button>
              <button
                onClick={() => submit("chakshu")}
                disabled={!packageId || submitting !== null}
                className="w-full rounded-xl border border-consumer-accent/30 py-3 font-semibold text-consumer-accent disabled:opacity-60"
              >
                {submitting === "chakshu" ? "Submitting…" : "Report to Chakshu"}
              </button>
            </>
          )}
          <button
            onClick={onDismiss}
            className="flex w-full items-center justify-center gap-1 py-2 text-sm text-consumer-muted"
          >
            <PhoneOff size={14} /> Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
