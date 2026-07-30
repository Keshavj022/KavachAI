import { LucideIcon } from "lucide-react";

/** Neutral placeholder for screens filled in later build phases. */
export default function Placeholder({
  icon: Icon,
  title,
  body,
  tone = "consumer",
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  tone?: "consumer" | "authority";
}) {
  const muted =
    tone === "authority" ? "text-authority-muted" : "text-consumer-muted";
  const ink = tone === "authority" ? "text-authority-text" : "text-consumer-ink";
  const accent =
    tone === "authority" ? "text-authority-cyan" : "text-consumer-accent";
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
      <Icon size={40} className={accent} strokeWidth={1.6} />
      <h2 className={`font-display text-lg font-semibold ${ink}`}>{title}</h2>
      <p className={`max-w-xs text-sm ${muted}`}>{body}</p>
    </div>
  );
}
