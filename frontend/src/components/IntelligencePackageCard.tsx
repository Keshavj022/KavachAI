import { useState } from "react";
import { Copy, FileLock2, Network, ShieldCheck } from "lucide-react";
import type { DecoyPackage } from "../api/client";

/**
 * Displays the extracted evidence from a decoy call: identifiers, amounts, the
 * claimed agency/officer, the pre-templated FIR narrative, and the encrypted
 * evidence note. Every identifier has a copy button.
 */
export default function IntelligencePackageCard({ pkg }: { pkg: DecoyPackage }) {
  const id = pkg.identifiers;
  const rows: { label: string; values: string[] }[] = [
    { label: "UPI", values: id.upis },
    { label: "Account", values: id.accounts },
    { label: "IFSC", values: id.ifsc },
    { label: "Phone", values: id.phones },
    { label: "Amount", values: pkg.amounts_demanded.map((a) => a.raw) },
    { label: "Agency claimed", values: pkg.agency_claimed },
    { label: "Officer claimed", values: pkg.officer_name_claimed },
    { label: "Station claimed", values: pkg.station_claimed },
    { label: "FIR/case quoted", values: pkg.fir_number_claimed },
    { label: "URL", values: id.urls },
  ].filter((r) => r.values.length > 0);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-consumer-ink">
          What they revealed
        </h3>
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.label} className="flex items-start gap-2">
              <span className="mt-0.5 w-28 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-consumer-muted">
                {r.label}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {r.values.map((v) => (
                  <CopyPill key={v} value={v} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {(pkg.ring_id || pkg.prior_report_count > 0) && (
        <div className="flex items-start gap-2 rounded-2xl border border-verdict-danger/20 bg-verdict-danger/5 p-3">
          <Network size={16} className="mt-0.5 text-verdict-danger" />
          <p className="text-sm text-consumer-ink">
            These identifiers match a known fraud ring
            {pkg.prior_report_count > 0
              ? ` — linked to ${pkg.prior_report_count} prior report${
                  pkg.prior_report_count > 1 ? "s" : ""
                }.`
              : "."}
          </p>
        </div>
      )}

      <div className="rounded-2xl border border-gray-200 bg-white p-4">
        <h3 className="mb-2 text-sm font-semibold text-consumer-ink">
          FIR-ready summary
        </h3>
        <p className="text-sm leading-relaxed text-consumer-muted">
          {pkg.fir_narrative}
        </p>
      </div>

      <div className="flex items-start gap-2 rounded-2xl border border-gray-200 bg-consumer-bg p-3">
        <FileLock2 size={16} className="mt-0.5 text-consumer-accent" />
        <div>
          <p className="text-sm font-medium text-consumer-ink">
            Audio evidence secured and encrypted for authorities
          </p>
          <p className="mt-0.5 flex items-center gap-1 font-mono text-[11px] text-consumer-muted">
            <ShieldCheck size={11} className="text-verdict-safe" />
            SHA-256 {pkg.audio_sha256.slice(0, 24)}…
          </p>
        </div>
      </div>
    </div>
  );
}

function CopyPill({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard?.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      className="group flex items-center gap-1 rounded-lg border border-consumer-accent/30 bg-consumer-accent/5 px-2 py-1 font-mono text-xs text-consumer-ink"
    >
      {value}
      <Copy size={11} className="text-consumer-muted opacity-0 transition group-hover:opacity-100" />
      {copied && <span className="text-[10px] text-verdict-safe">copied</span>}
    </button>
  );
}
