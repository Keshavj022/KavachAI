import { ShieldCheck, ShieldAlert, ShieldX } from "lucide-react";
import type { Verdict } from "../api/types";

/**
 * Verdict pill. Always pairs colour with an icon + label (never colour alone)
 * so it reads for colour-blind users and at a glance.
 */
const CONFIG: Record<
  Verdict,
  { label: string; icon: typeof ShieldCheck; classes: string }
> = {
  safe: {
    label: "Safe",
    icon: ShieldCheck,
    classes: "bg-verdict-safe/10 text-verdict-safe ring-verdict-safe/30",
  },
  suspicious: {
    label: "Suspicious",
    icon: ShieldAlert,
    classes: "bg-verdict-suspicious/10 text-verdict-suspicious ring-verdict-suspicious/30",
  },
  scam: {
    label: "Scam",
    icon: ShieldX,
    classes: "bg-verdict-danger/10 text-verdict-danger ring-verdict-danger/30",
  },
};

export default function VerdictBadge({
  verdict,
  size = "md",
}: {
  verdict: Verdict;
  size?: "sm" | "md";
}) {
  const { label, icon: Icon, classes } = CONFIG[verdict];
  const pad = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";
  const iconSize = size === "sm" ? 13 : 16;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold ring-1 ${classes} ${pad}`}
    >
      <Icon size={iconSize} strokeWidth={2.4} aria-hidden />
      {label}
    </span>
  );
}
