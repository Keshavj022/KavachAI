import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Globe } from "lucide-react";
import { LANGUAGES } from "../i18n/languages";
import { changeLanguage } from "../i18n/config";

/**
 * Persistent language switcher for the consumer top bar. Shows a globe + the
 * current language's native name; the dropdown lists every language by its own
 * native name (never ISO codes). Selection persists and applies RTL for Urdu.
 */
export default function LanguageToggle({
  tone = "consumer",
}: {
  tone?: "consumer" | "authority";
}) {
  const { i18n, t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  const current = LANGUAGES.find((l) => l.code === i18n.language) ?? LANGUAGES[0];

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const text =
    tone === "authority" ? "text-authority-text" : "text-consumer-ink";
  const muted =
    tone === "authority" ? "text-authority-muted" : "text-consumer-muted";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={t("lang.choose")}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`flex items-center gap-1.5 rounded-full border border-black/10 px-2.5 py-1 text-sm font-medium ${text} transition hover:bg-black/5`}
      >
        <Globe size={15} className={muted} />
        <span>{current.nativeName}</span>
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute right-0 z-50 mt-2 max-h-72 w-44 overflow-y-auto rounded-xl border border-gray-200 bg-white p-1 shadow-xl"
        >
          {LANGUAGES.map((lang) => {
            const active = lang.code === i18n.language;
            return (
              <button
                key={lang.code}
                role="option"
                aria-selected={active}
                onClick={() => {
                  changeLanguage(lang.code);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm transition ${
                  active
                    ? "bg-consumer-accent/10 text-consumer-accent"
                    : "text-consumer-ink hover:bg-gray-50"
                }`}
                dir={lang.dir}
              >
                <span>
                  <span className="block font-medium">{lang.nativeName}</span>
                  <span className="block text-[11px] text-consumer-muted">
                    {lang.englishName}
                  </span>
                </span>
                {active && <Check size={15} className="text-consumer-accent" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
