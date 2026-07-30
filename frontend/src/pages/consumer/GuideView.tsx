import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion, useInView } from "framer-motion";
import { AlertTriangle, Ban, Clock, Phone, Scale, Share2 } from "lucide-react";
import { api, GuideContacts } from "../../api/client";
import { Priya, RajuUncle, Scammer, Son } from "../../components/guide/Characters";

const CHAPTERS = ["one", "two", "three", "four", "five"] as const;

export default function GuideView() {
  const { t, i18n } = useTranslation();
  const [contacts, setContacts] = useState<GuideContacts | null>(null);
  const [activeChapter, setActiveChapter] = useState(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.guideContacts(i18n.language).then(setContacts).catch(() => setContacts(null));
  }, [i18n.language]);

  return (
    <div ref={scrollRef} className="relative h-full overflow-y-auto bg-consumer-bg">
      {/* Sticky progress */}
      <div className="sticky top-0 z-30 bg-consumer-surface/95 px-4 py-2 backdrop-blur">
        <div className="flex items-center justify-between">
          <span className="font-display text-sm font-bold text-consumer-ink">
            {t("guide.title")}
          </span>
          <span className="text-[11px] font-medium text-consumer-muted">
            {t("guide.progress", { current: activeChapter + 1, total: 5 })}
          </span>
        </div>
        <div className="mt-1.5 flex gap-1">
          {CHAPTERS.map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors ${
                i <= activeChapter ? "bg-consumer-accent" : "bg-gray-200"
              }`}
            />
          ))}
        </div>
      </div>

      <Chapter1 onView={() => setActiveChapter(0)} />
      <Chapter2 onView={() => setActiveChapter(1)} />
      <Chapter3 onView={() => setActiveChapter(2)} />
      <Chapter4 onView={() => setActiveChapter(3)} contacts={contacts} />
      <Chapter5 onView={() => setActiveChapter(4)} contacts={contacts} />

      <footer className="space-y-2 bg-consumer-surface px-5 py-6 text-center">
        <p className="text-[11px] text-consumer-muted">{t("guide.footer.attribution")}</p>
        <p className="text-[11px] leading-relaxed text-consumer-muted">
          {t("guide.footer.disclaimer")}
        </p>
      </footer>
    </div>
  );
}

// --- Reusable chapter shell ------------------------------------------------
function ChapterShell({
  tint,
  kicker,
  title,
  onView,
  children,
}: {
  tint: string;
  kicker: string;
  title: string;
  onView: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLElement | null>(null);
  const inView = useInView(ref, { amount: 0.4 });
  useEffect(() => {
    if (inView) onView();
  }, [inView, onView]);
  return (
    <section ref={ref} className="px-5 py-8" style={{ background: tint }}>
      <p className="text-[11px] font-semibold uppercase tracking-widest text-consumer-muted">
        {kicker}
      </p>
      <h2 className="mt-1 font-display text-2xl font-bold leading-tight text-consumer-ink">
        {title}
      </h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.5, delay }}
    >
      {children}
    </motion.div>
  );
}

function SpeechBubble({ side, text }: { side: "left" | "right"; text: string }) {
  return (
    <div className={`flex ${side === "right" ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm italic leading-snug ${
          side === "left"
            ? "rounded-bl-sm bg-consumer-ink/90 text-white"
            : "rounded-br-sm bg-white text-consumer-ink shadow-sm"
        }`}
      >
        {text}
      </div>
    </div>
  );
}

// --- Chapter 1 -------------------------------------------------------------
function Chapter1({ onView }: { onView: () => void }) {
  const { t } = useTranslation();
  const arc = [
    { key: "authority", icon: "📞" },
    { key: "accusation", icon: "😨" },
    { key: "isolation", icon: "🔒" },
    { key: "money", icon: "💸" },
  ] as const;
  return (
    <ChapterShell tint="#FFF5F5" kicker={t("guide.chapters.one.kicker")}
                  title={t("guide.chapters.one.title")} onView={onView}>
      <p className="mb-5 text-sm leading-relaxed text-consumer-muted">
        {t("guide.c1.intro")}
      </p>

      {/* Split scene */}
      <div className="mb-5 grid grid-cols-2 gap-3">
        <Reveal>
          <div className="flex flex-col items-center rounded-2xl bg-white p-3 shadow-sm">
            <motion.div animate={{ scale: [1, 1.02, 1] }} transition={{ duration: 3, repeat: Infinity }}>
              <RajuUncle emotion="frightened" size={96} />
            </motion.div>
            <p className="mt-1 text-[10px] uppercase tracking-wide text-consumer-muted">
              {t("guide.c1.victimLabel")}
            </p>
            <p className="text-xs font-semibold text-consumer-ink">{t("guide.c1.victimName")}</p>
          </div>
        </Reveal>
        <Reveal delay={0.1}>
          <div className="flex flex-col items-center rounded-2xl bg-consumer-ink p-3">
            <Scammer size={90} />
            <p className="mt-1 text-[10px] uppercase tracking-wide text-white/60">
              {t("guide.c1.operationLabel")}
            </p>
            <p className="text-xs font-semibold text-white">{t("guide.c1.operationName")}</p>
          </div>
        </Reveal>
      </div>

      {/* Dialogue */}
      <div className="mb-5 space-y-2">
        <SpeechBubble side="left" text={t("guide.c1.dialogue.scammer1")} />
        <SpeechBubble side="right" text={t("guide.c1.dialogue.raju1")} />
        <SpeechBubble side="left" text={t("guide.c1.dialogue.scammer2")} />
      </div>

      {/* Key fact */}
      <Reveal>
        <div className="mb-5 rounded-xl bg-consumer-accent p-4 text-white">
          <p className="text-lg font-bold leading-snug">{t("guide.c1.keyFactHeadline")}</p>
          <p className="mt-2 font-mono text-[11px] text-white/80">
            — {t("guide.c1.keyFactSource")}
          </p>
        </div>
      </Reveal>

      {/* Supporting facts */}
      <ul className="mb-6 space-y-2">
        {["loss", "targets", "arc"].map((k) => (
          <li key={k} className="flex items-start gap-2 text-sm text-consumer-ink">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-verdict-danger" />
            {t(`guide.c1.facts.${k}`)}
          </li>
        ))}
      </ul>

      {/* Arc timeline */}
      <div className="flex items-stretch gap-1">
        {arc.map((s, i) => (
          <div key={s.key} className="flex flex-1 items-center">
            <Reveal delay={i * 0.12}>
              <div className="rounded-xl bg-white p-2 text-center shadow-sm">
                <div className="text-xl">{s.icon}</div>
                <p className="mt-1 text-[10px] font-semibold text-consumer-ink">
                  {t(`guide.c1.arc.${s.key}.label`)}
                </p>
                <p className="text-[9px] leading-tight text-consumer-muted">
                  {t(`guide.c1.arc.${s.key}.line`)}
                </p>
              </div>
            </Reveal>
            {i < arc.length - 1 && <span className="px-0.5 text-consumer-muted">→</span>}
          </div>
        ))}
      </div>
    </ChapterShell>
  );
}

// --- Chapter 2 -------------------------------------------------------------
function Chapter2({ onView }: { onView: () => void }) {
  const { t } = useTranslation();
  const words = t("guide.c2.words", { returnObjects: true }) as string[];
  const signs = ["s1", "s2", "s3", "s4", "s5", "s6"];
  return (
    <ChapterShell tint="#F0FAFA" kicker={t("guide.chapters.two.kicker")}
                  title={t("guide.chapters.two.title")} onView={onView}>
      <p className="mb-4 text-sm leading-relaxed text-consumer-muted">{t("guide.c2.intro")}</p>

      <Reveal>
        <div className="mb-2 flex items-center gap-3 rounded-2xl bg-white p-3 shadow-sm">
          <motion.div initial={{ y: 4 }} whileInView={{ y: 0 }}>
            <RajuUncle emotion="determined" size={72} />
          </motion.div>
          <p className="text-base font-semibold italic text-consumer-ink">
            {t("guide.c2.rajuLine")}
          </p>
        </div>
      </Reveal>
      <p className="mb-5 text-xs text-consumer-muted">{t("guide.c2.rajuAfter")}</p>

      <p className="mb-2 text-sm font-medium text-consumer-ink">{t("guide.c2.fiveWordsIntro")}</p>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {(Array.isArray(words) ? words : []).map((w, i) => (
          <motion.span
            key={i}
            initial={{ scale: 0.7, opacity: 0 }}
            whileInView={{ scale: 1, opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.12, type: "spring", stiffness: 200 }}
            className="rounded-lg bg-consumer-accent px-3 py-2 text-sm font-bold uppercase text-white"
          >
            {w}
          </motion.span>
        ))}
      </div>
      <p className="mb-6 rounded-xl border border-consumer-accent/30 bg-white px-3 py-2 text-center text-lg font-bold text-consumer-accent">
        {t("guide.c2.phrase")}
      </p>

      <p className="mb-3 font-display text-lg font-bold text-consumer-ink">
        {t("guide.c2.signsIntro")}
      </p>
      <div className="space-y-2.5">
        {signs.map((s, i) => (
          <Reveal key={s} delay={i * 0.05}>
            <div className="flex gap-3 rounded-xl bg-white p-3 shadow-sm">
              <Ban size={18} className="mt-0.5 shrink-0 text-verdict-danger" />
              <div>
                <p className="text-sm font-semibold text-consumer-ink">
                  {t(`guide.c2.signs.${s}.title`)}
                </p>
                <p className="mt-0.5 text-xs italic text-consumer-muted">
                  {t(`guide.c2.signs.${s}.quote`)}
                </p>
                <p className="mt-1 text-xs text-consumer-ink">
                  {t(`guide.c2.signs.${s}.detail`)}
                </p>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </ChapterShell>
  );
}

// --- Chapter 3 -------------------------------------------------------------
function Chapter3({ onView }: { onView: () => void }) {
  const { t } = useTranslation();
  const rights = ["r1", "r2", "r3", "r4", "r5", "r6"];
  return (
    <ChapterShell tint="#FFFFFF" kicker={t("guide.chapters.three.kicker")}
                  title={t("guide.chapters.three.title")} onView={onView}>
      <div className="mb-5 flex items-center gap-3">
        <Priya size={84} />
        <p className="text-sm leading-relaxed text-consumer-muted">{t("guide.c3.intro")}</p>
      </div>
      <div className="space-y-3">
        {rights.map((r, i) => (
          <Reveal key={r} delay={i * 0.05}>
            <div className="rounded-xl border border-blue-100 bg-white p-4 shadow-sm">
              <div className="flex items-start gap-2">
                <Scale size={17} className="mt-0.5 shrink-0 text-consumer-accent" />
                <p className="text-sm font-semibold text-consumer-ink">
                  {t(`guide.c3.rights.${r}.title`)}
                </p>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-consumer-muted">
                {t(`guide.c3.rights.${r}.body`)}
              </p>
              <p className="mt-2 font-mono text-[10px] text-consumer-muted">
                {t("common.source")}: {t(`guide.c3.rights.${r}.source`)}
              </p>
            </div>
          </Reveal>
        ))}
      </div>
    </ChapterShell>
  );
}

// --- Chapter 4 -------------------------------------------------------------
function Chapter4({ onView, contacts }: { onView: () => void; contacts: GuideContacts | null }) {
  const { t } = useTranslation();
  const steps = ["s1", "s2", "s3", "s4"];
  const clockRef = useRef<HTMLDivElement | null>(null);
  const clockInView = useInView(clockRef, { once: true, amount: 0.6 });
  const [minutes, setMinutes] = useState(60);

  useEffect(() => {
    if (!clockInView) return;
    // Visual countdown: 60 → 0 over ~15 seconds (the effect, not a real timer).
    const start = Date.now();
    const id = window.setInterval(() => {
      const elapsed = (Date.now() - start) / 1000;
      const remaining = Math.max(0, Math.round(60 - (elapsed / 15) * 60));
      setMinutes(remaining);
      if (remaining <= 0) window.clearInterval(id);
    }, 250);
    return () => window.clearInterval(id);
  }, [clockInView]);

  return (
    <ChapterShell tint="#FFFBF0" kicker={t("guide.chapters.four.kicker")}
                  title={t("guide.chapters.four.title")} onView={onView}>
      <p className="mb-5 text-sm leading-relaxed text-consumer-muted">{t("guide.c4.intro")}</p>

      {/* Countdown clock */}
      <div ref={clockRef} className="mb-6 flex flex-col items-center">
        <div className="relative flex h-28 w-28 items-center justify-center rounded-full border-4 border-verdict-suspicious/30">
          <Clock size={20} className="absolute top-3 text-verdict-suspicious" />
          <div className="text-center">
            <span className="font-mono text-4xl font-bold tabular-nums text-verdict-suspicious">
              {minutes}
            </span>
            <p className="text-[10px] uppercase tracking-wide text-consumer-muted">
              {t("guide.c4.clockLabel")}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {steps.map((s, i) => (
          <Reveal key={s} delay={i * 0.08}>
            <div className="rounded-xl bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="rounded-full bg-verdict-suspicious/10 px-2 py-0.5 text-[10px] font-semibold text-verdict-suspicious">
                  {t(`guide.c4.steps.${s}.when`)}
                </span>
                <span className="font-mono text-[10px] text-consumer-muted">
                  {t(`guide.c4.steps.${s}.remaining`)}
                </span>
              </div>
              <p className="mt-2 flex items-center gap-2 text-sm font-semibold text-consumer-ink">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-consumer-accent text-[11px] text-white">
                  {i + 1}
                </span>
                {t(`guide.c4.steps.${s}.title`)}
              </p>
              {s === "s1" && (
                <a href="tel:1930" className="mt-2 flex items-center justify-center gap-2 rounded-lg bg-consumer-accent py-2.5 text-lg font-bold text-white">
                  <Phone size={18} /> 1930
                </a>
              )}
              <p className="mt-2 text-xs leading-relaxed text-consumer-muted">
                {t(`guide.c4.steps.${s}.body`)}
              </p>
              {s === "s2" && contacts && (
                <div className="mt-2">
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-consumer-muted">
                    {t("guide.c4.steps.s2.banksLabel")}
                  </p>
                  <div className="max-h-36 space-y-1 overflow-y-auto">
                    {contacts.bank_fraud_helplines.map((b) => (
                      <a key={b.name} href={b.tel_link}
                         className="flex items-center justify-between rounded-lg bg-consumer-bg px-2.5 py-1.5 text-xs">
                        <span className="text-consumer-ink">{b.name}</span>
                        <span className="font-mono text-consumer-accent">{b.number}</span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Reveal>
        ))}
      </div>

      <div className="mt-6 rounded-xl bg-white p-4 shadow-sm">
        <p className="mb-2 text-sm font-semibold text-consumer-ink">{t("guide.c4.afterTitle")}</p>
        <ul className="space-y-1.5">
          {["a1", "a2", "a3", "a4"].map((a) => (
            <li key={a} className="flex items-start gap-2 text-xs text-consumer-muted">
              <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-consumer-accent" />
              {t(`guide.c4.after.${a}`)}
            </li>
          ))}
        </ul>
      </div>
    </ChapterShell>
  );
}

// --- Chapter 5 -------------------------------------------------------------
function Chapter5({ onView, contacts }: { onView: () => void; contacts: GuideContacts | null }) {
  const { t, i18n } = useTranslation();
  const cardRef = useRef<HTMLDivElement | null>(null);
  const [busy, setBusy] = useState(false);

  async function shareCard() {
    if (!cardRef.current) return;
    setBusy(true);
    try {
      const { default: html2canvas } = await import("html2canvas");
      const canvas = await html2canvas(cardRef.current, {
        scale: 2, // retina-sharp
        backgroundColor: "#141A22",
        logging: false,
        useCORS: true,
      });
      const blob: Blob | null = await new Promise((r) => canvas.toBlob(r, "image/png"));
      if (!blob) return;
      const file = new File([blob], `kavach-safety-card-${i18n.language}.png`, {
        type: "image/png",
      });
      // Mobile: native share sheet (WhatsApp etc.). Desktop: download.
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: t("guide.c5.cardTitle") });
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = file.name;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch {
      /* user cancelled share or canvas failed — no-op */
    } finally {
      setBusy(false);
    }
  }

  const ref = useRef<HTMLElement | null>(null);
  const inView = useInView(ref, { amount: 0.3 });
  useEffect(() => {
    if (inView) onView();
  }, [inView, onView]);

  return (
    <section ref={ref} className="bg-consumer-bg px-5 py-8">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-consumer-muted">
        {t("guide.chapters.five.kicker")}
      </p>
      <h2 className="mt-1 font-display text-2xl font-bold text-consumer-ink">
        {t("guide.chapters.five.title")}
      </h2>

      {/* The shareable reference card (dark, photocopiable) */}
      <div ref={cardRef} className="mt-5 rounded-2xl bg-authority-base p-5 text-white">
        <p className="text-center text-[11px] font-semibold uppercase tracking-widest text-authority-cyan">
          {t("guide.c5.cardTitle")}
        </p>
        <p className="mb-4 text-center text-xs text-white/60">{t("guide.c5.cardSubtitle")}</p>

        <div className="space-y-2.5">
          {(contacts?.helplines ?? []).map((h) => (
            <div key={h.number} className="flex items-baseline justify-between gap-3">
              <span className="font-mono text-lg font-bold text-authority-cyan">{h.number}</span>
              <span className="text-right text-[11px] leading-tight text-white/80">{h.name}</span>
            </div>
          ))}
          {(contacts?.portals ?? []).slice(0, 4).map((p) => (
            <div key={p.url} className="flex items-baseline justify-between gap-3">
              <span className="truncate font-mono text-xs text-authority-cyan">
                {p.url.replace("https://", "")}
              </span>
              <span className="shrink-0 text-right text-[11px] text-white/80">
                {p.name.split(" — ")[0]}
              </span>
            </div>
          ))}
        </div>

        <div className="mt-4 border-t border-white/15 pt-3">
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-white/70">
            {t("guide.c5.remember.title")}
          </p>
          <ul className="space-y-1">
            {["r1", "r2", "r3", "r4"].map((r) => (
              <li key={r} className="flex items-start gap-1.5 text-[11px] text-white/90">
                <span className="text-verdict-safe">✓</span>
                {t(`guide.c5.remember.${r}`)}
              </li>
            ))}
          </ul>
        </div>
        <p className="mt-3 text-center font-display text-xs font-bold tracking-wide text-white/50">
          KAVACH
        </p>
      </div>

      <button
        onClick={shareCard}
        disabled={busy || !contacts}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-consumer-accent py-3 font-semibold text-white disabled:opacity-60"
      >
        <Share2 size={18} />
        {busy ? t("guide.c5.generating") : t("guide.c5.share")}
      </button>
      <p className="mt-2 flex items-center justify-center gap-1 text-center text-xs text-consumer-muted">
        <AlertTriangle size={12} /> {t("guide.c5.shareHint")}
      </p>

      {/* farewell characters */}
      <div className="mt-6 flex items-end justify-center gap-1 opacity-90">
        <RajuUncle emotion="relieved" size={56} />
        <Priya size={52} />
        <Son size={50} />
      </div>
    </section>
  );
}
