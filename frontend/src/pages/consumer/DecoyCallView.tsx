import { useCallback, useEffect, useRef, useState } from "react";
import { PhoneIncoming, ShieldCheck } from "lucide-react";
import IncomingCallInterstitial from "../../components/IncomingCallInterstitial";
import DecoyLiveView from "../../components/DecoyLiveView";
import ScamVerdictScreen from "../../components/ScamVerdictScreen";
import { api, WS_BASE, getToken } from "../../api/client";
import type {
  AgentMode,
  DecoyDetection,
  DecoyFrame,
  DecoyIdentifier,
  ScamStage,
  SpokenLine,
  TranscriptTurn,
} from "../../api/decoyTypes";

type Phase = "idle" | "incoming" | "live" | "ended";
type Speaker = "scammer" | "agent" | null;

// One playable unit in the conversation queue. A greeting has only an agent
// line; a full turn has the caller line, the detection it produced, and the
// reply. The queue plays these in order so audio and transcript stay in sync.
interface QueueItem {
  scammer?: SpokenLine;
  detection?: DecoyDetection;
  mode?: AgentMode;
  agent?: SpokenLine;
}

interface EndedPayload {
  verdict: "scam" | "safe";
  package_id?: string;
}

// The simulated caller uses the seeded known-scammer number so the flagged
// badge shows (real OS-level call interception is out of scope — see README).
const DEMO_CALLER = "+919812345678";

// Each option seeds the generative fraudster — the caller's lines are authored
// live by the local LLM, so no two calls are the same.
const SCRIPT_OPTIONS = [
  { id: "digital_arrest", label: "Digital arrest (Hindi)", lang: "hi" },
  { id: "tech_support", label: "Tech support (English)", lang: "en" },
];

// How long a text-only line is shown when no voice clip is available — paced to
// a natural speaking rate so the transcript still reads in real time.
function estimateMs(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.min(7000, Math.max(1500, words * 360));
}

export default function DecoyCallView() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [script, setScript] = useState(SCRIPT_OPTIONS[0]);
  const [flagged, setFlagged] = useState<boolean | null>(null);

  // Live state driven by the playback queue.
  const [mode, setMode] = useState<AgentMode>("monitor");
  const [confidence, setConfidence] = useState(0);
  const [stage, setStage] = useState<ScamStage>("none");
  const [identifiers, setIdentifiers] = useState<DecoyIdentifier[]>([]);
  const [identifierCount, setIdentifierCount] = useState(0);
  const [knownRing, setKnownRing] = useState(false);
  const [agentLine, setAgentLine] = useState("");
  const [activeSpeaker, setActiveSpeaker] = useState<Speaker>(null);
  const [transcript, setTranscript] = useState<TranscriptTurn[]>([]);
  const [duration, setDuration] = useState(0);

  const [verdict, setVerdict] = useState<"scam" | "safe">("safe");
  const [packageId, setPackageId] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const startRef = useRef<number>(0);
  const timerRef = useRef<number | null>(null);

  // Playback-queue machinery.
  const queueRef = useRef<QueueItem[]>([]);
  const playingRef = useRef(false);
  const endedRef = useRef<EndedPayload | null>(null);
  // Bumped on every start/teardown; async playback checks it and bails if stale,
  // so a queue from an old call can never drive the UI after a new one begins.
  const runRef = useRef(0);
  const fallbackTimerRef = useRef<number | null>(null);

  useEffect(() => () => teardown(), []);

  // Look up the caller's flagged status for the interstitial badge.
  useEffect(() => {
    api
      .lookupIdentifier(DEMO_CALLER)
      .then((r) => setFlagged(r.known_scammer))
      .catch(() => setFlagged(null));
  }, []);

  function teardown() {
    runRef.current += 1; // invalidate any in-flight playback
    queueRef.current = [];
    playingRef.current = false;
    endedRef.current = null;
    if (fallbackTimerRef.current) {
      window.clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
    const el = audioRef.current;
    if (el) {
      el.onended = null;
      el.onerror = null;
      try {
        el.pause();
      } catch {
        /* no-op */
      }
    }
    wsRef.current?.close();
    wsRef.current = null;
    if (timerRef.current) window.clearInterval(timerRef.current);
  }

  function resetLive() {
    setMode("monitor");
    setConfidence(0);
    setStage("none");
    setIdentifiers([]);
    setIdentifierCount(0);
    setKnownRing(false);
    setAgentLine("");
    setActiveSpeaker(null);
    setTranscript([]);
    setDuration(0);
  }

  const handleFrame = useCallback((frame: DecoyFrame) => {
    switch (frame.type) {
      case "turn":
        queueRef.current.push({
          scammer: frame.scammer ?? undefined,
          detection: frame.detection ?? undefined,
          mode: frame.mode,
          agent: frame.agent ?? undefined,
        });
        pump();
        break;
      case "call_ended":
        // Defer the verdict screen until the queue finishes playing so the last
        // lines are actually heard/read before the call ends.
        endedRef.current = { verdict: frame.verdict, package_id: frame.package_id };
        pump();
        break;
      case "error":
        break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Drive the queue: play the next item, or finalize once drained + ended. */
  function pump() {
    if (playingRef.current) return;
    const next = queueRef.current.shift();
    if (!next) {
      if (endedRef.current) finalizeEnded(endedRef.current);
      return;
    }
    playingRef.current = true;
    const run = runRef.current;
    playItem(next, run).finally(() => {
      playingRef.current = false;
      if (runRef.current === run) pump();
    });
  }

  async function playItem(item: QueueItem, run: number) {
    // Caller line first: reveal the bubble as the voice plays.
    if (item.scammer) {
      setActiveSpeaker("scammer");
      appendTranscript("scammer", item.scammer);
      await speak(item.scammer.audio_url, item.scammer.text, run);
      if (runRef.current !== run) return;
    }
    // The detection this line produced lands as it finishes — meter climbs,
    // chips appear, mode badge updates — right before Ramesh answers.
    if (item.detection) applyDetection(item.detection);
    if (item.mode) setMode(item.mode);

    if (item.agent) {
      setActiveSpeaker("agent");
      setAgentLine(item.agent.text);
      appendTranscript("agent", item.agent);
      await speak(item.agent.audio_url, item.agent.text, run);
      if (runRef.current !== run) return;
    }
    setActiveSpeaker(null);
  }

  /** Resolve when the line's clip finishes — or, if audio can't play, after a
   *  text-length fallback. Guarded so a stalled fetch or a missing `ended`
   *  event can never hang the playback queue. */
  function speak(url: string | null, text: string, run: number): Promise<void> {
    return new Promise((resolve) => {
      if (runRef.current !== run) return resolve();
      const el = audioRef.current;
      const estMs = estimateMs(text);
      const timers: number[] = [];
      let settled = false;
      const setTimer = (ms: number) => {
        const id = window.setTimeout(() => finish(), ms);
        timers.push(id);
        fallbackTimerRef.current = id;
        return id;
      };
      const finish = () => {
        if (settled) return;
        settled = true;
        timers.forEach(window.clearTimeout);
        if (el) {
          el.onended = null;
          el.onerror = null;
          el.oncanplay = null;
        }
        resolve();
      };

      if (!url || !el) {
        setTimer(estMs);
        return;
      }
      el.src = `${apiBase()}${url}`;
      el.onended = finish;
      el.onerror = () => setTimer(estMs);
      // If the clip hasn't even begun within a few seconds (backend busy
      // synthesizing), stop waiting on it and pace from the text so the
      // conversation keeps moving instead of freezing on one line.
      let started = false;
      el.oncanplay = () => {
        started = true;
      };
      const stallGuard = window.setTimeout(() => {
        if (!started) finish();
      }, 3500);
      timers.push(stallGuard);
      // Absolute cap: a played clip fires `ended`, but if the event is ever
      // dropped this guarantees the queue still advances.
      setTimer(Math.max(estMs, 12000));
      el.play().catch(() => setTimer(estMs));
    });
  }

  function appendTranscript(speaker: "scammer" | "agent", line: SpokenLine) {
    setTranscript((t) => [...t, { speaker, text: line.text, language: line.language }]);
  }

  function applyDetection(d: DecoyDetection) {
    setConfidence(d.scam_prob);
    setStage(d.stage);
    setKnownRing(d.known_ring_hit);
    setIdentifierCount(d.identifiers_total);
    if (d.new_identifiers.length) {
      setIdentifiers((prev) => {
        const seen = new Set(prev.map((p) => `${p.type}:${p.value}`));
        const add = d.new_identifiers.filter((n) => !seen.has(`${n.type}:${n.value}`));
        return [...prev, ...add];
      });
    }
  }

  function finalizeEnded(payload: EndedPayload) {
    setVerdict(payload.verdict);
    setPackageId(payload.package_id ?? null);
    setActiveSpeaker(null);
    setPhase("ended");
    teardown();
  }

  async function startDecoy() {
    teardown(); // close any prior socket/queue so old frames can't clobber this call
    resetLive();
    setPhase("live");
    const run = (runRef.current += 1);
    try {
      const res = await api.startDecoy(script.lang, script.id, true);
      if (runRef.current !== run) return;
      // The decoy's greeting arrives as the first WebSocket turn (voiced live),
      // so nothing is enqueued from the REST response here.
      const token = getToken();
      const ws = new WebSocket(`${WS_BASE}/api/decoy/ws/${res.session_id}?token=${token}`);
      wsRef.current = ws;
      startRef.current = Date.now();
      timerRef.current = window.setInterval(
        () => setDuration((Date.now() - startRef.current) / 1000),
        250,
      );
      ws.onopen = () => ws.send(JSON.stringify({ type: "start", scenario: script.id }));
      ws.onmessage = (ev) => handleFrame(JSON.parse(ev.data) as DecoyFrame);
      ws.onerror = () => setPhase("ended");
    } catch {
      setPhase("idle");
    }
  }

  return (
    <div className="relative h-full">
      <audio ref={audioRef} className="hidden" />

      {phase === "idle" && (
        <IdleView
          script={script}
          setScript={setScript}
          onRing={() => setPhase("incoming")}
        />
      )}

      {phase === "incoming" && (
        <IncomingCallInterstitial
          callerNumber={DEMO_CALLER}
          flaggedReports={flagged ? 14 : null}
          onLetKavach={startDecoy}
          onTakeIt={() => setPhase("idle")}
        />
      )}

      {phase === "live" && (
        <DecoyLiveView
          demoMode
          mode={mode}
          durationSeconds={duration}
          confidence={confidence}
          stage={stage}
          identifiers={identifiers}
          identifierCount={identifierCount}
          agentLine={agentLine}
          activeSpeaker={activeSpeaker}
          knownRing={knownRing}
          transcript={transcript}
        />
      )}

      {phase === "ended" && (
        <ScamVerdictScreen
          verdict={verdict}
          packageId={packageId}
          durationSeconds={duration}
          onDismiss={() => setPhase("idle")}
          onNewCall={() => setPhase("idle")}
        />
      )}
    </div>
  );
}

function IdleView({
  script,
  setScript,
  onRing,
}: {
  script: (typeof SCRIPT_OPTIONS)[number];
  setScript: (s: (typeof SCRIPT_OPTIONS)[number]) => void;
  onRing: () => void;
}) {
  return (
    <div className="flex h-full flex-col justify-between px-5 py-6">
      <div>
        <div className="mb-5 flex flex-col items-center text-center">
          <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-consumer-accent/10">
            <ShieldCheck size={28} className="text-consumer-accent" />
          </div>
          <h1 className="font-display text-xl font-bold text-consumer-ink">
            AI Decoy
          </h1>
          <p className="mt-1 text-sm text-consumer-muted">
            Kavach answers a suspicious call in your place, playing a flustered,
            cooperative version of you to waste the scammer's time and draw out
            their details. The scammer talks to the AI, never to you.
          </p>
        </div>

        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-consumer-muted">
          Scenario
        </p>
        <div className="space-y-2">
          {SCRIPT_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => setScript(opt)}
              className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left transition ${
                script.id === opt.id
                  ? "border-consumer-accent bg-consumer-accent/5"
                  : "border-gray-200 hover:border-consumer-accent/40"
              }`}
            >
              <span className="text-sm font-semibold text-consumer-ink">
                {opt.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={onRing}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-consumer-accent py-4 text-lg font-semibold text-white transition hover:bg-consumer-accent-dark"
      >
        <PhoneIncoming size={20} /> Simulate incoming call
      </button>
    </div>
  );
}

function apiBase(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
}
