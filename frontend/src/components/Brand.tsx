import { Shield } from "lucide-react";

/** Kavach wordmark + shield glyph. `tone` adapts to the two app surfaces. */
export default function Brand({
  tone = "consumer",
  size = "md",
}: {
  tone?: "consumer" | "authority";
  size?: "sm" | "md" | "lg";
}) {
  const text =
    tone === "authority" ? "text-authority-text" : "text-consumer-ink";
  const accent =
    tone === "authority" ? "text-authority-cyan" : "text-consumer-accent";
  const dims =
    size === "lg" ? "text-2xl" : size === "sm" ? "text-base" : "text-xl";
  const icon = size === "lg" ? 30 : size === "sm" ? 18 : 24;

  return (
    <div className="flex items-center gap-2">
      <Shield className={accent} size={icon} strokeWidth={2.4} aria-hidden />
      <span className={`font-display font-bold tracking-tight ${dims} ${text}`}>
        Kavach
      </span>
    </div>
  );
}
