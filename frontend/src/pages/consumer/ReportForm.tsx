import { FormEvent, useMemo, useState } from "react";
import { CheckCircle2, FileWarning, ShieldAlert } from "lucide-react";
import { api } from "../../api/client";
import type { ScamCategory } from "../../api/types";
import { useCallStore } from "../../store/call";

const CATEGORIES: { value: ScamCategory; label: string }[] = [
  { value: "digital_arrest", label: "Digital arrest" },
  { value: "kyc_update", label: "KYC update" },
  { value: "investment", label: "Investment" },
  { value: "fake_delivery", label: "Fake delivery" },
  { value: "refund", label: "Refund" },
  { value: "loan", label: "Loan" },
  { value: "other", label: "Other" },
];

const CITIES = ["Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Jaipur", "Kolkata", "Pune"];
const CITY_COORDS: Record<string, [number, number]> = {
  Delhi: [28.6139, 77.209],
  Mumbai: [19.076, 72.8777],
  Bengaluru: [12.9716, 77.5946],
  Hyderabad: [17.385, 78.4867],
  Jaipur: [26.9124, 75.7873],
  Kolkata: [22.5726, 88.3639],
  Pune: [18.5204, 73.8567],
};

export default function ReportForm() {
  const lastDetection = useCallStore((s) => s.lastDetection);
  const clear = useCallStore((s) => s.clear);

  const [category, setCategory] = useState<ScamCategory>(
    lastDetection?.category ?? "digital_arrest",
  );
  const [channel] = useState(lastDetection?.channel ?? "call");
  const [content, setContent] = useState(lastDetection?.content ?? "");
  const [identifier, setIdentifier] = useState("");
  const [city, setCity] = useState("Delhi");
  const [notify, setNotify] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ id: number; alerts: number } | null>(null);

  const prefilled = useMemo(() => Boolean(lastDetection), [lastDetection]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const [lat, lng] = CITY_COORDS[city];
      const report = await api.createReport({
        call_session_id: lastDetection?.sessionId ?? null,
        channel,
        scam_category: category,
        content,
        location_label: city,
        location_lat: lat,
        location_lng: lng,
        identifier_values: identifier ? [identifier] : [],
        notify_contacts: notify,
      });
      setResult({ id: report.id, alerts: report.alerts_sent ?? 0 });
      clear();
    } catch {
      setError("Could not file the report. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
        <CheckCircle2 size={48} className="text-verdict-safe" />
        <h2 className="font-display text-xl font-bold text-consumer-ink">
          Report filed
        </h2>
        <p className="text-sm text-consumer-muted">
          Report #{result.id} was submitted. The identifiers you reported now
          protect the next person contacted by them.
        </p>
        {result.alerts > 0 && (
          <p className="rounded-xl bg-consumer-accent/10 px-4 py-2 text-sm font-medium text-consumer-accent">
            {result.alerts} trusted contact{result.alerts > 1 ? "s" : ""} alerted.
          </p>
        )}
        <button
          onClick={() => setResult(null)}
          className="mt-2 rounded-xl border border-consumer-accent/30 px-4 py-2 text-sm font-semibold text-consumer-accent"
        >
          File another
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex h-full flex-col">
      <div className="border-b border-black/5 bg-consumer-surface px-4 py-3">
        <h1 className="flex items-center gap-2 font-display text-lg font-bold text-consumer-ink">
          <FileWarning size={20} className="text-consumer-accent" />
          File a report
        </h1>
        {prefilled && (
          <p className="mt-1 flex items-center gap-1 text-xs text-consumer-accent">
            <ShieldAlert size={13} /> Pre-filled from your last check
          </p>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-consumer-ink">
            Scam type
          </span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as ScamCategory)}
            className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-consumer-accent"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-consumer-ink">
            Scammer number / UPI / account
          </span>
          <input
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="e.g. +919812345678"
            className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-consumer-accent"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-consumer-ink">
            What happened
          </span>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={5}
            required
            placeholder="Describe the call or message…"
            className="w-full resize-none rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-consumer-accent"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-consumer-ink">
            City
          </span>
          <select
            value={city}
            onChange={(e) => setCity(e.target.value)}
            className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-consumer-accent"
          >
            {CITIES.map((cc) => (
              <option key={cc}>{cc}</option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-3 rounded-xl border border-gray-200 px-3 py-3">
          <input
            type="checkbox"
            checked={notify}
            onChange={(e) => setNotify(e.target.checked)}
            className="h-5 w-5 accent-consumer-accent"
          />
          <span className="text-sm text-consumer-ink">
            Alert my trusted contacts
          </span>
        </label>

        {error && (
          <p role="alert" className="rounded-lg bg-verdict-danger/10 px-3 py-2 text-sm text-verdict-danger">
            {error}
          </p>
        )}
      </div>

      <div className="border-t border-black/5 bg-consumer-surface p-3">
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-consumer-accent py-3 font-semibold text-white disabled:opacity-60"
        >
          {busy ? "Filing…" : "File report"}
        </button>
      </div>
    </form>
  );
}
