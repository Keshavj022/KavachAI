import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { Report } from "../../api/types";
import { CATEGORY_LABEL, IDENTIFIER_LABEL, statusLabel } from "./format";

export default function ReportsTable() {
  const navigate = useNavigate();
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listReports()
      .then(setReports)
      .catch(() => setError("Could not load reports."));
  }, []);

  if (error) return <p className="text-authority-red">{error}</p>;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl font-bold">Reports</h1>
        <p className="text-sm text-authority-muted">
          Every filed report, newest first.
        </p>
      </div>

      <div className="overflow-x-auto rounded-xl border border-authority-border bg-authority-surface">
        {reports === null ? (
          <p className="p-6 text-sm text-authority-muted">Loading…</p>
        ) : reports.length === 0 ? (
          <p className="p-6 text-center text-sm text-authority-muted">
            No reports yet. Filed reports appear here.
          </p>
        ) : (
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-authority-border text-xs uppercase tracking-wide text-authority-muted">
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Reporter</th>
                <th className="px-4 py-3 font-medium">Channel</th>
                <th className="px-4 py-3 font-medium">Location</th>
                <th className="px-4 py-3 font-medium">Identifiers</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Filed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-authority-border">
              {reports.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => navigate(`/authority/reports/${r.id}`)}
                  className="cursor-pointer transition hover:bg-white/5"
                >
                  <td className="px-4 py-3 font-mono text-authority-muted">#{r.id}</td>
                  <td className="px-4 py-3 font-medium">
                    {CATEGORY_LABEL[r.scam_category] ?? r.scam_category}
                  </td>
                  <td className="px-4 py-3">{r.reporter_name ?? "—"}</td>
                  <td className="px-4 py-3 capitalize text-authority-muted">{r.channel}</td>
                  <td className="px-4 py-3 text-authority-muted">
                    {r.location_label ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {r.identifiers.slice(0, 2).map((i) => (
                        <span
                          key={i.id}
                          className="rounded bg-authority-base px-1.5 py-0.5 font-mono text-[11px] text-authority-cyan"
                        >
                          {IDENTIFIER_LABEL[i.type] ?? i.type}
                        </span>
                      ))}
                      {r.identifiers.length > 2 && (
                        <span className="text-[11px] text-authority-muted">
                          +{r.identifiers.length - 2}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-authority-cyan/10 px-2 py-0.5 font-mono text-[11px] capitalize text-authority-cyan">
                      {statusLabel(r.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-authority-muted">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
