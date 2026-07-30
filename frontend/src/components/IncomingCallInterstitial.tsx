import { motion } from "framer-motion";
import { PhoneIncoming, ShieldCheck, User } from "lucide-react";

/**
 * Shown when a call comes in, before the user picks up. In this prototype the
 * incoming call is simulated (there is no OS-level call interception). The
 * decision must be clear in under two seconds — the user is under the stress of
 * a ringing phone.
 */
export default function IncomingCallInterstitial({
  callerNumber,
  flaggedReports,
  onLetKavach,
  onTakeIt,
}: {
  callerNumber: string;
  flaggedReports: number | null;
  onLetKavach: () => void;
  onTakeIt: () => void;
}) {
  return (
    <div className="flex h-full flex-col bg-consumer-bg">
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <motion.div
          animate={{ scale: [1, 1.06, 1] }}
          transition={{ duration: 1.4, repeat: Infinity }}
          className="mb-5 flex h-20 w-20 items-center justify-center rounded-full bg-consumer-accent/10"
        >
          <PhoneIncoming size={34} className="text-consumer-accent" />
        </motion.div>
        <p className="text-xs font-semibold uppercase tracking-wide text-consumer-muted">
          Incoming call
        </p>
        <p className="mt-1 font-mono text-2xl font-bold text-consumer-ink">
          {callerNumber}
        </p>
        <p className="mt-1 flex items-center gap-1 text-sm text-consumer-muted">
          <User size={14} /> Unknown number
        </p>

        {flaggedReports != null && flaggedReports > 0 && (
          <div className="mt-4 rounded-full bg-verdict-danger/10 px-4 py-1.5 text-sm font-semibold text-verdict-danger">
            Reported {flaggedReports} time{flaggedReports > 1 ? "s" : ""} as a scam
          </div>
        )}
      </div>

      <div className="space-y-3 px-6 pb-8">
        <button
          onClick={onLetKavach}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-consumer-accent py-4 text-lg font-semibold text-white transition hover:bg-consumer-accent-dark active:scale-[0.98]"
        >
          <ShieldCheck size={22} />
          Let Kavach talk
        </button>
        <button
          onClick={onTakeIt}
          className="w-full rounded-2xl border border-gray-200 py-3.5 text-base font-medium text-consumer-muted transition hover:border-consumer-accent/40"
        >
          I'll take it myself
        </button>
        <p className="pt-1 text-center text-xs text-consumer-muted">
          Kavach answers as a decoy so you never speak to a scammer.
        </p>
      </div>
    </div>
  );
}
