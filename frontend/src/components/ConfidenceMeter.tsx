import { motion } from "framer-motion";
import type { ScamStage } from "../api/types";

/**
 * Semicircular arc gauge. The fill climbs with confidence and shifts
 * green → amber → red. Below it, the four scam-arc stages act as a stepper so
 * the viewer can see *where in the scam* the caller is — the arc concept made
 * visible.
 */

const STAGES: { key: ScamStage; label: string }[] = [
  { key: "authority_claim", label: "Authority" },
  { key: "accusation", label: "Accusation" },
  { key: "isolation", label: "Isolation" },
  { key: "money_demand", label: "Money" },
];

const STAGE_ORDER: Record<ScamStage, number> = {
  none: 0,
  authority_claim: 1,
  accusation: 2,
  isolation: 3,
  money_demand: 4,
};

function colorFor(confidence: number): string {
  if (confidence >= 0.7) return "#D12E2E"; // danger
  if (confidence >= 0.4) return "#C77A0A"; // suspicious
  return "#1B8A5A"; // safe
}

export default function ConfidenceMeter({
  confidence,
  stage,
}: {
  confidence: number;
  stage: ScamStage;
}) {
  const pct = Math.round(confidence * 100);
  const color = colorFor(confidence);

  // Semicircle geometry.
  const radius = 78;
  const circumference = Math.PI * radius; // half circle
  const dash = circumference;
  const offset = circumference * (1 - Math.min(1, Math.max(0, confidence)));
  const reached = STAGE_ORDER[stage];

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-[110px] w-[190px]">
        <svg width="190" height="110" viewBox="0 0 190 110" aria-hidden>
          {/* Track */}
          <path
            d="M 12 100 A 78 78 0 0 1 178 100"
            fill="none"
            stroke="#E4E9F0"
            strokeWidth="14"
            strokeLinecap="round"
          />
          {/* Fill */}
          <motion.path
            d="M 12 100 A 78 78 0 0 1 178 100"
            fill="none"
            stroke={color}
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={dash}
            initial={false}
            animate={{ strokeDashoffset: offset, stroke: color }}
            transition={{ type: "spring", stiffness: 90, damping: 18 }}
          />
        </svg>
        <div className="absolute inset-x-0 bottom-1 flex flex-col items-center">
          <motion.span
            key={pct}
            initial={{ scale: 0.85, opacity: 0.6 }}
            animate={{ scale: 1, opacity: 1 }}
            className="font-mono text-3xl font-bold tabular-nums"
            style={{ color }}
          >
            {pct}
            <span className="text-lg">%</span>
          </motion.span>
          <span
            className="text-[11px] font-semibold uppercase tracking-wider"
            style={{ color }}
          >
            {confidence >= 0.7 ? "High risk" : confidence >= 0.4 ? "Caution" : "Monitoring"}
          </span>
        </div>
      </div>

      {/* Stage stepper */}
      <div
        className="mt-2 grid w-full grid-cols-4 gap-1"
        role="list"
        aria-label="Scam arc progress"
      >
        {STAGES.map((s, i) => {
          const active = reached >= i + 1;
          const isCurrent = reached === i + 1;
          return (
            <div key={s.key} className="flex flex-col items-center gap-1" role="listitem">
              <div
                className={`h-1.5 w-full rounded-full transition-colors ${
                  active ? "" : "bg-gray-200"
                }`}
                style={active ? { background: color } : undefined}
              />
              <span
                className={`text-center text-[9px] font-medium leading-tight ${
                  isCurrent
                    ? "text-consumer-ink"
                    : active
                      ? "text-consumer-muted"
                      : "text-gray-300"
                }`}
              >
                {s.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
