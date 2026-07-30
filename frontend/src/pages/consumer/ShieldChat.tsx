import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Send, ShieldCheck } from "lucide-react";
import VerdictBadge from "../../components/VerdictBadge";
import { api } from "../../api/client";
import type { VerdictOut } from "../../api/types";
import { useCallStore } from "../../store/call";

interface ChatItem {
  role: "user" | "guardian";
  text: string;
  verdict?: VerdictOut;
}

const EXAMPLES = [
  "Your bank KYC has expired. Account will be blocked today. Verify: http://sbi-kyc-update.in/verify",
  "This is CBI. A parcel in your name has drugs. Do not tell anyone, stay on the call.",
];

export default function ShieldChat() {
  const navigate = useNavigate();
  const setLastDetection = useCallStore((s) => s.setLastDetection);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const feedRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" });
  }, [items, busy]);

  async function check(content: string) {
    if (!content.trim() || busy) return;
    setInput("");
    setItems((prev) => [...prev, { role: "user", text: content }]);
    setBusy(true);
    try {
      const verdict = await api.checkMessage(content, "sms");
      setItems((prev) => [
        ...prev,
        { role: "guardian", text: verdict.explanation, verdict },
      ]);
    } catch {
      setItems((prev) => [
        ...prev,
        {
          role: "guardian",
          text: "Could not check that message. Please try again.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    check(input);
  }

  function report(item: ChatItem) {
    if (!item.verdict) return;
    setLastDetection({
      sessionId: null,
      channel: "sms",
      category: item.verdict.category,
      content: items.find((i) => i.role === "user")?.text ?? item.text,
      redFlags: item.verdict.red_flags,
      sources: item.verdict.sources,
      identifiers: [],
    });
    navigate("/app/report");
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-black/5 bg-consumer-surface px-4 py-3">
        <h1 className="font-display text-lg font-bold text-consumer-ink">
          Fraud Shield
        </h1>
        <p className="text-xs text-consumer-muted">
          Paste a suspicious SMS or message to check it.
        </p>
      </div>

      <div ref={feedRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {items.length === 0 && (
          <div className="mt-4 flex flex-col items-center text-center">
            <ShieldCheck size={34} className="mb-2 text-consumer-accent" />
            <p className="text-sm text-consumer-muted">
              No messages checked yet. Try an example:
            </p>
            <div className="mt-3 space-y-2">
              {EXAMPLES.map((ex, i) => (
                <button
                  key={i}
                  onClick={() => check(ex)}
                  className="block rounded-xl border border-gray-200 px-3 py-2 text-left text-xs text-consumer-ink hover:border-consumer-accent/40"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {items.map((item, i) =>
          item.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-consumer-accent px-3 py-2 text-sm text-white">
                {item.text}
              </div>
            </div>
          ) : (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-[88%] rounded-2xl rounded-bl-sm bg-white px-3 py-2.5 text-sm text-consumer-ink shadow-sm"
            >
              {item.verdict && (
                <div className="mb-1.5 flex items-center gap-2">
                  <VerdictBadge verdict={item.verdict.verdict} size="sm" />
                  {item.verdict.known_scammer && (
                    <span className="text-[11px] font-semibold text-verdict-danger">
                      Known scammer
                    </span>
                  )}
                </div>
              )}
              <p className="leading-relaxed">{item.text}</p>
              {item.verdict?.red_flags && item.verdict.red_flags.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {item.verdict.red_flags.slice(0, 4).map((f, j) => (
                    <li
                      key={j}
                      className="flex items-start gap-1.5 text-xs text-consumer-muted"
                    >
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-verdict-suspicious" />
                      {f}
                    </li>
                  ))}
                </ul>
              )}
              {item.verdict?.sources && item.verdict.sources.length > 0 && (
                <p className="mt-2 rounded-lg bg-consumer-bg px-2 py-1.5 text-[11px] text-consumer-muted">
                  <span className="font-semibold">Source: </span>
                  {item.verdict.sources[0].ref || item.verdict.sources[0].title}
                </p>
              )}
              {item.verdict && item.verdict.verdict !== "safe" && (
                <button
                  onClick={() => report(item)}
                  className="mt-2 text-xs font-semibold text-consumer-accent hover:underline"
                >
                  File a report →
                </button>
              )}
            </motion.div>
          ),
        )}

        {busy && (
          <div className="flex items-center gap-1 px-2 text-consumer-muted">
            <Dot /> <Dot /> <Dot />
          </div>
        )}
      </div>

      <form
        onSubmit={onSubmit}
        className="flex items-center gap-2 border-t border-black/5 bg-consumer-surface p-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Paste a message…"
          className="flex-1 rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-consumer-accent"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-consumer-accent text-white disabled:opacity-50"
          aria-label="Check message"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}

function Dot() {
  return (
    <motion.span
      className="h-2 w-2 rounded-full bg-consumer-muted"
      animate={{ opacity: [0.3, 1, 0.3] }}
      transition={{ duration: 1, repeat: Infinity }}
    />
  );
}
