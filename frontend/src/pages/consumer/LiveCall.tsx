import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { Phone, PhoneOff, Radio, Play, Mic, ShieldAlert, ShieldHalf, ChevronRight } from "lucide-react";
import ConfidenceMeter from "../../components/ConfidenceMeter";
import InterruptTakeover from "../../components/InterruptTakeover";
import VerdictBadge from "../../components/VerdictBadge";
import { api, WS_BASE, getToken } from "../../api/client";
import type { ScamStage, Source, Verdict, WSMessage } from "../../api/types";
import { useCallStore } from "../../store/call";

type Phase = "idle" | "live" | "ended";
type InputMode = "demo" | "live";
type Lang = "auto" | "en" | "hi";

const DEMO_OPTIONS: { id: string; label: string; hint: string }[] = [
  { id: "digital_arrest", label: "Digital arrest", hint: "CBI impersonation — the full scam arc" },
  { id: "kyc_update", label: "Fake KYC", hint: "Bank impersonation — stays a warning" },
  { id: "benign", label: "Normal call", hint: "Control — never interrupts" },
];

// How often (ms) to cut a complete, independently-decodable audio clip and send
// it. A stop/start cycle (not timeslice) is used so each blob has its own
// container header and can be transcribed on its own.
const CHUNK_MS = 3000;

export default function LiveCall() {
  const navigate = useNavigate();
  const setLastDetection = useCallStore((s) => s.setLastDetection);

  const [phase, setPhase] = useState<Phase>("idle");
  const [inputMode, setInputMode] = useState<InputMode>("demo");
  const [language, setLanguage] = useState<Lang>("auto");
  const [script, setScript] = useState("digital_arrest");

  const [lines, setLines] = useState<string[]>([]);
  const [confidence, setConfidence] = useState(0);
  const [stage, setStage] = useState<ScamStage>("none");
  const [verdict, setVerdict] = useState<Verdict>("safe");
  const [knownScammer, setKnownScammer] = useState(false);
  const [redFlags, setRedFlags] = useState<string[]>([]);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [showInterrupt, setShowInterrupt] = useState(false);
  const [warn, setWarn] = useState(false);
  const [detector, setDetector] = useState("fallback");
  const [micError, setMicError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const sessionRef = useRef<number | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  // Mic capture refs.
  const recorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunkTimerRef = useRef<number | null>(null);
  const recordingRef = useRef(false);

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight });
  }, [lines]);

  // Clean up socket + mic on unmount.
  useEffect(() => () => teardown(), []);

  function resetState() {
    setLines([]);
    setConfidence(0);
    setStage("none");
    setVerdict("safe");
    setKnownScammer(false);
    setRedFlags([]);
    setExplanation(null);
    setSources([]);
    setShowInterrupt(false);
    setWarn(false);
    setMicError(null);
    setDetector("fallback");
  }

  async function startCall() {
    resetState();
    try {
      const { session_id } = await api.startCall();
      sessionRef.current = session_id;
      const token = getToken();
      const ws = new WebSocket(`${WS_BASE}/ws/call/${session_id}?token=${token}`);
      wsRef.current = ws;
      ws.onopen = () => {
        setPhase("live");
        if (inputMode === "demo") {
          ws.send(JSON.stringify({ action: "start", mode: "demo", script, language }));
        } else {
          ws.send(JSON.stringify({ action: "start", mode: "live", language }));
          startMic(ws);
        }
      };
      ws.onmessage = (ev) => handleFrame(JSON.parse(ev.data) as WSMessage);
      ws.onerror = () => setPhase("ended");
    } catch {
      setPhase("idle");
    }
  }

  async function startMic(ws: WebSocket) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "";
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recorderRef.current = rec;
      recordingRef.current = true;

      rec.ondataavailable = (e) => {
        // Each blob is a complete clip; send it as a binary frame. Audio is
        // transcribed locally on the backend and discarded — it is never stored.
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };
      // When a clip stops, immediately start the next one (if still recording).
      rec.onstop = () => {
        if (recordingRef.current && rec.state === "inactive") rec.start();
      };
      rec.start();
      // Periodically cut a clip: stop → emits a full blob → onstop restarts.
      chunkTimerRef.current = window.setInterval(() => {
        if (rec.state === "recording") rec.stop();
      }, CHUNK_MS);
    } catch {
      setMicError(
        "Microphone permission is required for live mode. Switch to Demo mode to continue.",
      );
      setPhase("ended");
    }
  }

  function stopMic() {
    recordingRef.current = false;
    if (chunkTimerRef.current) {
      clearInterval(chunkTimerRef.current);
      chunkTimerRef.current = null;
    }
    try {
      recorderRef.current?.state !== "inactive" && recorderRef.current?.stop();
    } catch {
      /* already stopped */
    }
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    recorderRef.current = null;
    mediaStreamRef.current = null;
  }

  function teardown() {
    stopMic();
    wsRef.current?.close();
    wsRef.current = null;
  }

  function handleFrame(f: WSMessage) {
    setLines(f.partial_transcript.split("\n").filter(Boolean));
    setConfidence(f.confidence);
    setStage(f.stage);
    setVerdict(f.verdict);
    setKnownScammer(f.known_scammer);
    setRedFlags(f.red_flags);
    setWarn(f.warn && !f.interrupt);
    setDetector(f.detector);
    if (f.explanation) setExplanation(f.explanation);
    if (f.sources.length) setSources(f.sources);
    if (f.interrupt) setShowInterrupt((prev) => prev || true);
    if (f.done) {
      stopMic();
      setPhase("ended");
      wsRef.current?.close();
    }
  }

  function endCall() {
    // Live mode: tell the server to finalize; demo mode ends on its own.
    if (inputMode === "live" && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "stop" }));
    }
    stopMic();
    if (sessionRef.current) api.endCall(sessionRef.current).catch(() => {});
    setPhase("ended");
  }

  function goReport() {
    setLastDetection({
      sessionId: sessionRef.current,
      channel: "call",
      category: verdict === "safe" ? "other" : "digital_arrest",
      content: lines.join("\n"),
      redFlags,
      sources,
      identifiers: [],
    });
    navigate("/app/report");
  }

  return (
    <div className="relative flex h-full flex-col">
      {/* Privacy / listening indicator. */}
      <div className="flex items-center justify-between px-4 py-2">
        <div className="flex items-center gap-2">
          {phase === "live" ? (
            <>
              <span className="flex h-2 w-2 animate-pulse rounded-full bg-verdict-danger" />
              <span className="text-xs font-medium text-consumer-muted">
                {inputMode === "live"
                  ? "Listening · transcribed on-device, audio not stored"
                  : "Analyzing · audio kept in memory, not stored"}
              </span>
            </>
          ) : (
            <span className="text-xs font-medium text-consumer-muted">
              Guardian ready
            </span>
          )}
        </div>
        {phase !== "idle" && <VerdictBadge verdict={verdict} size="sm" />}
      </div>

      {/* Meter */}
      {phase !== "idle" && (
        <div className="border-y border-black/5 bg-consumer-surface px-4 py-4">
          <ConfidenceMeter confidence={confidence} stage={stage} />
          {knownScammer && (
            <p className="mt-2 text-center text-xs font-semibold text-verdict-danger">
              Known scammer — already reported by the network
            </p>
          )}
          <p className="mt-1 text-center text-[10px] uppercase tracking-wide text-gray-400">
            assessment: {detector === "groq" ? "cloud few-shot model" : "on-device rules"}
          </p>
        </div>
      )}

      {/* Soft warning strip (pre-interrupt cue). */}
      <AnimatePresence>
        {warn && phase === "live" && !showInterrupt && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center gap-2 bg-verdict-suspicious/10 px-4 py-2 text-xs font-medium text-verdict-suspicious"
          >
            <ShieldAlert size={14} />
            This call is showing scam warning signs. Stay cautious.
          </motion.div>
        )}
      </AnimatePresence>

      {/* Body */}
      {phase === "idle" ? (
        <IdleView
          inputMode={inputMode}
          setInputMode={setInputMode}
          language={language}
          setLanguage={setLanguage}
          script={script}
          setScript={setScript}
          onStart={startCall}
        />
      ) : (
        <>
          <div
            ref={transcriptRef}
            className="flex-1 space-y-2 overflow-y-auto px-4 py-3"
          >
            {micError && (
              <p className="rounded-lg bg-verdict-danger/10 px-3 py-2 text-sm text-verdict-danger">
                {micError}
              </p>
            )}
            {lines.length === 0 && inputMode === "live" && !micError && (
              <p className="mt-6 text-center text-sm text-consumer-muted">
                Speak into your microphone. The transcript appears here as it is
                recognized.
              </p>
            )}
            {lines.map((line, i) => (
              <TranscriptLine key={i} text={line} />
            ))}
          </div>

          {phase === "ended" && verdict !== "safe" && (
            <EndSummary
              verdict={verdict}
              explanation={explanation}
              sources={sources}
              onReport={goReport}
            />
          )}

          <div className="border-t border-black/5 bg-consumer-surface p-3">
            {phase === "live" ? (
              <button
                onClick={endCall}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-verdict-danger py-3 font-semibold text-white"
              >
                <PhoneOff size={18} /> End call
              </button>
            ) : (
              <button
                onClick={() => setPhase("idle")}
                className="w-full rounded-xl border border-consumer-accent/30 py-3 font-semibold text-consumer-accent"
              >
                New call
              </button>
            )}
          </div>
        </>
      )}

      {/* Signature interrupt */}
      <AnimatePresence>
        {showInterrupt && (
          <InterruptTakeover
            redFlags={redFlags}
            explanation={explanation}
            sources={sources}
            onDismiss={() => setShowInterrupt(false)}
            onReport={goReport}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function IdleView({
  inputMode,
  setInputMode,
  language,
  setLanguage,
  script,
  setScript,
  onStart,
}: {
  inputMode: InputMode;
  setInputMode: (m: InputMode) => void;
  language: Lang;
  setLanguage: (l: Lang) => void;
  script: string;
  setScript: (s: string) => void;
  onStart: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-1 flex-col justify-between px-5 py-6">
      <div>
        {/* Home-screen safety-guide entry point */}
        <Link
          to="/app/guide"
          className="mb-5 flex items-center gap-3 rounded-2xl border border-consumer-accent/20 bg-consumer-accent/5 p-3 transition hover:bg-consumer-accent/10"
        >
          <ShieldHalf size={22} className="shrink-0 text-consumer-accent" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-consumer-ink">
              {t("home.learnTitle")}
            </p>
            <p className="truncate text-xs text-consumer-muted">{t("home.learnBody")}</p>
          </div>
          <ChevronRight size={18} className="shrink-0 text-consumer-accent" />
        </Link>

        <div className="mb-5 flex flex-col items-center text-center">
          <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-consumer-accent/10">
            <Phone size={28} className="text-consumer-accent" />
          </div>
          <h1 className="font-display text-xl font-bold text-consumer-ink">
            Live call guard
          </h1>
          <p className="mt-1 text-sm text-consumer-muted">
            Kavach watches the call and interrupts if it turns into a scam —
            before any money is asked for.
          </p>
        </div>

        {/* Input mode toggle */}
        <div className="mb-4 grid grid-cols-2 gap-2">
          <ModeButton
            active={inputMode === "demo"}
            onClick={() => setInputMode("demo")}
            icon={Radio}
            label="Demo mode"
            hint="Scripted, reliable"
          />
          <ModeButton
            active={inputMode === "live"}
            onClick={() => setInputMode("live")}
            icon={Mic}
            label="Live mic"
            hint="Speak in real time"
          />
        </div>

        {inputMode === "demo" ? (
          <>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-consumer-muted">
              Demo scenario
            </p>
            <div className="space-y-2">
              {DEMO_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setScript(opt.id)}
                  className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left transition ${
                    script === opt.id
                      ? "border-consumer-accent bg-consumer-accent/5"
                      : "border-gray-200 hover:border-consumer-accent/40"
                  }`}
                >
                  <Radio
                    size={18}
                    className={
                      script === opt.id ? "text-consumer-accent" : "text-gray-300"
                    }
                  />
                  <span>
                    <span className="block text-sm font-semibold text-consumer-ink">
                      {opt.label}
                    </span>
                    <span className="block text-xs text-consumer-muted">
                      {opt.hint}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-gray-200 p-3">
            <p className="text-sm text-consumer-ink">
              Your microphone is transcribed on your device. Only the text is
              analyzed — the audio is never stored or uploaded.
            </p>
            <div className="mt-3">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-consumer-muted">
                Language
              </p>
              <div className="flex gap-2">
                {(["auto", "en", "hi"] as Lang[]).map((l) => (
                  <button
                    key={l}
                    onClick={() => setLanguage(l)}
                    className={`flex-1 rounded-lg border px-2 py-1.5 text-xs font-medium capitalize transition ${
                      language === l
                        ? "border-consumer-accent bg-consumer-accent/5 text-consumer-accent"
                        : "border-gray-200 text-consumer-muted"
                    }`}
                  >
                    {l === "auto" ? "Auto" : l === "en" ? "English" : "Hindi"}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      <button
        onClick={onStart}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-consumer-accent py-4 text-lg font-semibold text-white transition hover:bg-consumer-accent-dark"
      >
        {inputMode === "demo" ? <Play size={20} /> : <Mic size={20} />}
        {inputMode === "demo" ? "Start monitored call" : "Start listening"}
      </button>
    </div>
  );
}

function ModeButton({
  active,
  onClick,
  icon: Icon,
  label,
  hint,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof Radio;
  label: string;
  hint: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center gap-1 rounded-xl border p-3 transition ${
        active
          ? "border-consumer-accent bg-consumer-accent/5"
          : "border-gray-200 hover:border-consumer-accent/40"
      }`}
    >
      <Icon size={20} className={active ? "text-consumer-accent" : "text-gray-400"} />
      <span className="text-sm font-semibold text-consumer-ink">{label}</span>
      <span className="text-[11px] text-consumer-muted">{hint}</span>
    </button>
  );
}

function TranscriptLine({ text }: { text: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl bg-white px-3 py-2 text-sm text-consumer-ink shadow-sm"
    >
      {text}
    </motion.div>
  );
}

function EndSummary({
  verdict,
  explanation,
  sources,
  onReport,
}: {
  verdict: Verdict;
  explanation: string | null;
  sources: Source[];
  onReport: () => void;
}) {
  return (
    <div className="border-t border-black/5 bg-consumer-surface px-4 py-3">
      <div className="mb-2 flex items-center gap-2">
        <VerdictBadge verdict={verdict} />
        <span className="text-sm font-semibold text-consumer-ink">
          Call summary
        </span>
      </div>
      {explanation && (
        <p className="text-sm leading-relaxed text-consumer-muted">{explanation}</p>
      )}
      {sources.length > 0 && (
        <p className="mt-2 rounded-lg bg-consumer-bg px-3 py-2 text-xs text-consumer-muted">
          <span className="font-semibold">Source: </span>
          {sources[0].ref || sources[0].title}
        </p>
      )}
      <button
        onClick={onReport}
        className="mt-3 w-full rounded-xl bg-consumer-accent py-3 font-semibold text-white"
      >
        File a report
      </button>
    </div>
  );
}
