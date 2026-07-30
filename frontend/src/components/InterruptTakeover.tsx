import { motion } from "framer-motion";
import { PhoneOff, ShieldX, X } from "lucide-react";
import type { Source } from "../api/types";

/**
 * THE signature moment. A full-bleed red overlay that slams in and breaks the
 * victim's trance. Copy is authoritative and de-escalating: one verdict line,
 * one reassurance, one clear action. Respects prefers-reduced-motion via the
 * global CSS rule that neutralises animation durations.
 */
export default function InterruptTakeover({
  redFlags,
  explanation,
  sources,
  onDismiss,
  onReport,
}: {
  redFlags: string[];
  explanation: string | null;
  sources: Source[];
  onDismiss: () => void;
  onReport: () => void;
}) {
  return (
    <motion.div
      role="alertdialog"
      aria-modal="true"
      aria-label="Scam warning"
      initial={{ opacity: 0, scale: 1.08 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className="absolute inset-0 z-40 flex flex-col bg-interrupt text-white"
    >
      {/* Pulsing ring accent at the top */}
      <div className="flex flex-col items-center px-6 pt-12">
        <motion.div
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.08, type: "spring", stiffness: 140, damping: 12 }}
          className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-white/15 ring-4 ring-white/30 animate-pulse-ring"
        >
          <ShieldX size={44} strokeWidth={2.4} />
        </motion.div>
        <h1 className="text-center font-display text-3xl font-bold leading-tight">
          This is a scam
        </h1>
        <p className="mt-3 text-center text-lg font-medium leading-snug text-white/95">
          Real police never arrest you over a video call. You are not in
          trouble.
        </p>
      </div>

      {/* Explanation + red flags */}
      <div className="mt-5 flex-1 overflow-y-auto px-6">
        {explanation && (
          <p className="rounded-2xl bg-white/10 p-4 text-sm leading-relaxed text-white/95">
            {explanation}
          </p>
        )}
        {redFlags.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {redFlags.slice(0, 5).map((flag, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-white/90">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-white/70" />
                {flag}
              </li>
            ))}
          </ul>
        )}
        {sources.length > 0 && (
          <div className="mt-4 rounded-xl border border-white/20 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-white/70">
              Why we know
            </p>
            <p className="mt-1 text-sm text-white/90">{sources[0].snippet}</p>
            <p className="mt-1 text-[11px] italic text-white/60">
              {sources[0].ref || sources[0].title}
            </p>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="space-y-3 p-6">
        <button
          onClick={onDismiss}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white py-4 text-lg font-bold text-interrupt shadow-lg transition active:scale-[0.98]"
        >
          <PhoneOff size={22} strokeWidth={2.5} />
          Hang up now
        </button>
        <button
          onClick={onReport}
          className="w-full rounded-2xl border border-white/40 py-3 text-base font-semibold text-white transition hover:bg-white/10"
        >
          File a report
        </button>
        <button
          onClick={onDismiss}
          className="flex w-full items-center justify-center gap-1 py-1 text-sm text-white/70 hover:text-white"
        >
          <X size={14} />
          Dismiss
        </button>
      </div>
    </motion.div>
  );
}
