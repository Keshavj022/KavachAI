import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, MapPin } from "lucide-react";
import { api } from "../../api/client";
import type { Report } from "../../api/types";
import { CATEGORY_LABEL, IDENTIFIER_LABEL, riskColor, statusLabel } from "./format";
import EvidencePanel from "./EvidencePanel";

export default function CaseDetail() {
  const { id } = useParams();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .getReport(Number(id))
      .then(setReport)
      .catch(() => setError("Could not load this case."));
  }, [id]);

  if (error) return <p className="text-authority-red">{error}</p>;
  if (!report) return <p className="text-sm text-authority-muted">Loading…</p>;

  return (
    <div className="max-w-4xl space-y-5">
      <Link
        to="/authority/reports"
        className="inline-flex items-center gap-1 text-sm text-authority-muted hover:text-authority-text"
      >
        <ArrowLeft size={15} /> Back to reports
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold">
            {CATEGORY_LABEL[report.scam_category] ?? report.scam_category}
          </h1>
          <p className="font-mono text-sm text-authority-muted">
            Case #{report.id} · reported by {report.reporter_name ?? "—"}
          </p>
        </div>
        <span className="rounded-full bg-authority-cyan/10 px-3 py-1 font-mono text-xs capitalize text-authority-cyan">
          {statusLabel(report.status)}
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <InfoCard label="Channel" value={report.channel} />
        <InfoCard
          label="Location"
          value={report.location_label ?? "Unknown"}
          icon={report.location_label ? MapPin : undefined}
        />
        <InfoCard
          label="Filed"
          value={new Date(report.created_at).toLocaleString()}
        />
      </div>

      <Panel title="Report content">
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-authority-text">
          {report.content || "No description provided."}
        </p>
      </Panel>

      <Panel title={`Linked identifiers (${report.identifiers.length})`}>
        {report.identifiers.length === 0 ? (
          <p className="text-sm text-authority-muted">
            No identifiers extracted from this report.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase text-authority-muted">
                  <th className="py-2 font-medium">Type</th>
                  <th className="py-2 font-medium">Value</th>
                  <th className="py-2 font-medium">Risk</th>
                  <th className="py-2 font-medium">Reports</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-authority-border">
                {report.identifiers.map((i) => (
                  <tr key={i.id}>
                    <td className="py-2">{IDENTIFIER_LABEL[i.type] ?? i.type}</td>
                    <td className="py-2 font-mono text-authority-cyan">{i.value}</td>
                    <td className="py-2">
                      <span
                        className="rounded px-1.5 py-0.5 font-mono text-xs"
                        style={{
                          background: `${riskColor(i.risk_score)}22`,
                          color: riskColor(i.risk_score),
                        }}
                      >
                        {i.risk_score.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-2 text-authority-muted">{i.report_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <EvidencePanel reportId={report.id} />
    </div>
  );
}

function InfoCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon?: typeof MapPin;
}) {
  return (
    <div className="rounded-xl border border-authority-border bg-authority-surface p-3">
      <p className="text-[10px] uppercase tracking-wide text-authority-muted">
        {label}
      </p>
      <p className="mt-1 flex items-center gap-1 text-sm font-medium capitalize">
        {Icon && <Icon size={14} className="text-authority-cyan" />}
        {value}
      </p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-authority-border bg-authority-surface p-4">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {children}
    </div>
  );
}
