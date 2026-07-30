import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, FileText, Network, ShieldAlert } from "lucide-react";
import { api, StatsData } from "../../api/client";
import type { Report } from "../../api/types";
import { CATEGORY_LABEL, statusLabel } from "./format";

export default function Dashboard() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const [s, r] = await Promise.all([api.stats(), api.listReports()]);
        if (!alive) return;
        setStats(s);
        setReports(r);
      } catch {
        if (alive) setError("Could not load dashboard data.");
      }
    }
    tick();
    // Live feed: poll every 5s so newly filed reports appear during the demo.
    const id = setInterval(tick, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (error) {
    return <p className="text-authority-red">{error}</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold">Command Dashboard</h1>
        <p className="text-sm text-authority-muted">
          Live view of reported fraud and network intelligence.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={FileText} label="Total reports" value={stats?.total_reports ?? "—"} accent="cyan" />
        <StatCard icon={ShieldAlert} label="High-risk identifiers" value={stats?.high_risk_identifiers ?? "—"} accent="red" />
        <StatCard icon={Network} label="Active rings" value={stats?.active_rings ?? "—"} accent="amber" />
        <StatCard icon={AlertTriangle} label="Tracked identifiers" value={stats?.total_identifiers ?? "—"} accent="cyan" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Reports · last 7 days">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={stats?.trend ?? []}>
              <defs>
                <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22B8CF" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#22B8CF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#26303F" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: "#8A97AC", fontSize: 11 }}
                tickFormatter={(d: string) => d.slice(5)}
              />
              <YAxis tick={{ fill: "#8A97AC", fontSize: 11 }} allowDecimals={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Area type="monotone" dataKey="count" stroke="#22B8CF" strokeWidth={2} fill="url(#trendFill)" />
            </AreaChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Reports by category">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart
              data={(stats?.categories ?? []).map((c) => ({
                name: CATEGORY_LABEL[c.category] ?? c.category,
                count: c.count,
              }))}
            >
              <CartesianGrid stroke="#26303F" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: "#8A97AC", fontSize: 10 }} />
              <YAxis tick={{ fill: "#8A97AC", fontSize: 11 }} allowDecimals={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "#ffffff08" }} />
              <Bar dataKey="count" fill="#E0A020" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      {/* Live reports feed */}
      <Panel title="Live report feed">
        {reports.length === 0 ? (
          <p className="py-6 text-center text-sm text-authority-muted">
            No reports yet. Filed reports appear here.
          </p>
        ) : (
          <ul className="divide-y divide-authority-border">
            {reports.slice(0, 8).map((r) => (
              <li key={r.id}>
                <Link
                  to={`/authority/reports/${r.id}`}
                  className="flex items-center justify-between gap-3 py-3 transition hover:bg-white/5"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {CATEGORY_LABEL[r.scam_category] ?? r.scam_category}
                      <span className="ml-2 text-xs text-authority-muted">
                        {r.reporter_name}
                      </span>
                    </p>
                    <p className="truncate text-xs text-authority-muted">
                      {r.location_label ?? "Unknown"} · {r.channel} ·{" "}
                      {new Date(r.created_at).toLocaleString()}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-authority-cyan/10 px-2 py-0.5 font-mono text-[11px] capitalize text-authority-cyan">
                    {statusLabel(r.status)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

const TOOLTIP_STYLE = {
  background: "#18212F",
  border: "1px solid #26303F",
  borderRadius: 8,
  color: "#E6EAF2",
  fontSize: 12,
};

const ACCENTS: Record<string, string> = {
  cyan: "text-authority-cyan",
  red: "text-authority-red",
  amber: "text-authority-amber",
};

function StatCard({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: typeof FileText;
  label: string;
  value: number | string;
  accent: "cyan" | "red" | "amber";
}) {
  return (
    <div className="rounded-xl border border-authority-border bg-authority-surface p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-authority-muted">
          {label}
        </span>
        <Icon size={18} className={ACCENTS[accent]} />
      </div>
      <p className="mt-2 font-mono text-3xl font-bold tabular-nums">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-authority-border bg-authority-surface p-4">
      <h2 className="mb-3 text-sm font-semibold text-authority-text">{title}</h2>
      {children}
    </div>
  );
}
