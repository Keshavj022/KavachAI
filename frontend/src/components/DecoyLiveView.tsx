import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Copy } from "lucide-react";
import ConfidenceMeter from "./ConfidenceMeter";
import type {
  AgentMode,
  DecoyIdentifier,
  ScamStage,
  TranscriptTurn,
} from "../api/decoyTypes";

const MODE_LABEL: Record<AgentMode, { label: string; classes: string }> = {
  monitor: { label: "Monitoring", classes: "bg-consumer-accent/10 text-consumer-accent" },
  stall: { label: "Stalling", classes: "bg-verdict-suspicious/10 text-verdict-suspicious" },
  wrap_up: { label: "Wrapping up", classes: "bg-verdict-danger/10 text-verdict-danger" },
};

// Only identifier kinds worth surfacing as evidence chips.
const CHIP_ORDER = ["upi", "account", "ifsc", "phone", "amount", "agency", "officer", "station", "fir", "url"];

export default function DecoyLiveView({
  demoMode,
  mode,
  durationSeconds,
  confidence,
  stage,
  identifiers,
  identifierCount,
  agentLine,
  activeSpeaker,
  knownRing,
  transcript,
}: {
  demoMode: boolean;
  mode: AgentMode;
  durationSeconds: number;
  confidence: number;
  stage: ScamStage;
  identifiers: DecoyIdentifier[];
  identifierCount: number;
  agentLine: string;
  activeSpeaker: "scammer" | "agent" | null;
  knownRing: boolean;
  transcript: TranscriptTurn[];
}) {
  const agentSpeaking = activeSpeaker === "agent";
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight });
  }, [transcript]);

  const chips = [...identifiers].sort(
    (a, b) => CHIP_ORDER.indexOf(a.type) - CHIP_ORDER.indexOf(b.type),
  );

  return (
    <div className="flex h-full flex-col">
      {/* Header: mode + timer + demo flag */}
      <div className="flex items-center justify-between border-b border-black/5 bg-consumer-surface px-4 py-2">
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${MODE_LABEL[mode].classes}`}>
          {MODE_LABEL[mode].label}
        </span>
        <div className="flex items-center gap-2">
          {demoMode && (
            <span className="rounded-full border border-consumer-muted/30 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-consumer-muted">
              Demo mode
            </span>
          )}
          <span className="font-mono text-sm tabular-nums text-consumer-ink">
            {formatDuration(durationSeconds)}
          </span>
        </div>
      </div>

      {/* Meter — the central element, watched as it climbs */}
      <div className="border-b border-black/5 bg-consumer-surface px-4 pb-3 pt-4">
        <div className="scale-110">
          <ConfidenceMeter confidence={confidence} stage={stage} />
        </div>
        <div className="mt-2 flex items-center justify-center gap-2 text-sm">
          <span className="font-semibold text-consumer-ink">{identifierCount}</span>
          <span className="text-consumer-muted">identifier{identifierCount === 1 ? "" : "s"} captured</span>
        </div>
        {knownRing && (
          <p className="mt-1 text-center text-xs font-semibold text-verdict-danger">
            Matches a known fraud ring
          </p>
        )}
      </div>

      {/* Agent status: waveform + Ramesh's last line */}
      <div className="flex items-start gap-3 border-b border-black/5 px-4 py-3">
        <Waveform active={agentSpeaking} />
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-consumer-muted">
            Kavach
          </p>
          <p className="mt-0.5 text-sm leading-snug text-consumer-ink">
            {agentLine || "…"}
          </p>
        </div>
      </div>

      {/* Identifier chips */}
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-2 border-b border-black/5 px-4 py-3">
          <AnimatePresence>
            {chips.map((id) => (
              <IdentifierChip key={`${id.type}:${id.value}`} id={id} />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Rolling transcript */}
      <div ref={transcriptRef} className="flex-1 space-y-2 overflow-y-auto px-4 py-3">
        {transcript.map((t, i) => {
          // The most recent bubble is the one currently being spoken aloud.
          const speaking = activeSpeaker !== null && i === transcript.length - 1;
          return (
            <div key={i} className={t.speaker === "scammer" ? "flex" : "flex justify-end"}>
              <div
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm transition ${
                  t.speaker === "scammer"
                    ? "rounded-bl-sm bg-verdict-danger/10 text-consumer-ink"
                    : "rounded-br-sm bg-white text-consumer-ink shadow-sm"
                } ${
                  speaking
                    ? t.speaker === "scammer"
                      ? "ring-2 ring-verdict-danger/40"
                      : "ring-2 ring-consumer-accent/40"
                    : ""
                }`}
              >
                <span className="mb-0.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-consumer-muted">
                  {speaking && (
                    <span
                      className={`inline-block h-1.5 w-1.5 animate-pulse rounded-full ${
                        t.speaker === "scammer" ? "bg-verdict-danger" : "bg-consumer-accent"
                      }`}
                      aria-hidden
                    />
                  )}
                  {t.speaker === "scammer" ? "Caller" : "Kavach"} · {t.language}
                </span>
                {t.text}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function IdentifierChip({ id }: { id: DecoyIdentifier }) {
  return (
    <motion.button
      initial={{ scale: 0.85, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.2 }}
      onClick={() => navigator.clipboard?.writeText(id.value)}
      title="Copy"
      className="group flex items-center gap-1.5 rounded-lg border border-consumer-accent/30 bg-consumer-accent/5 px-2 py-1"
    >
      <span className="text-[10px] font-semibold uppercase tracking-wide text-consumer-accent">
        {id.label}
      </span>
      <span className="font-mono text-xs text-consumer-ink">{id.value}</span>
      <Copy size={11} className="text-consumer-muted opacity-0 transition group-hover:opacity-100" />
    </motion.button>
  );
}

function Waveform({ active }: { active: boolean }) {
  return (
    <div className="flex h-8 items-center gap-0.5" aria-hidden>
      {[0, 1, 2, 3, 4].map((i) => (
        <motion.span
          key={i}
          className="w-1 rounded-full bg-consumer-accent"
          animate={active ? { height: [6, 22, 6] } : { height: 6 }}
          transition={{ duration: 0.6, repeat: active ? Infinity : 0, delay: i * 0.1 }}
          style={{ height: 6 }}
        />
      ))}
    </div>
  );
}

function formatDuration(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
