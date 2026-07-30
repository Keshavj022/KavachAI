import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { X } from "lucide-react";
import { api, NodeDetail } from "../../api/client";
import type { GraphData, GraphNode } from "../../api/types";
import { IDENTIFIER_LABEL, riskColor, CATEGORY_LABEL } from "./format";

export default function FraudGraph() {
  const [data, setData] = useState<GraphData | null>(null);
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [size, setSize] = useState({ w: 600, h: 480 });
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const fgRef = useRef<any>(null);

  useEffect(() => {
    api
      .graph()
      .then(setData)
      .catch(() => setError("Could not load the fraud graph."));
  }, []);

  // Spread the layout so rings are legible: stronger repulsion + longer links.
  useEffect(() => {
    if (!fgRef.current || !data) return;
    const fg = fgRef.current;
    fg.d3Force("charge")?.strength(-220);
    fg.d3Force("link")?.distance(55);
  }, [data]);

  // Size the canvas to its container.
  useEffect(() => {
    if (!wrapRef.current) return;
    const el = wrapRef.current;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [data]);

  // Clone so the force layout mutating source/target does not fight React.
  const graphData = useMemo(
    () =>
      data
        ? {
            nodes: data.nodes.map((n) => ({ ...n })),
            links: data.links.map((l) => ({ ...l })),
          }
        : { nodes: [], links: [] },
    [data],
  );

  async function onNodeClick(node: GraphNode) {
    try {
      setDetail(await api.graphNode(node.id));
    } catch {
      setError("Could not load node detail.");
    }
  }

  if (error) return <p className="text-authority-red">{error}</p>;

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <div className="mb-3 flex items-end justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Fraud network</h1>
          <p className="text-sm text-authority-muted">
            Identifiers clustered into rings. Click a node to inspect it.
          </p>
        </div>
        <Legend />
      </div>

      <div className="relative flex-1 overflow-hidden rounded-xl border border-authority-border bg-authority-base">
        <div ref={wrapRef} className="absolute inset-0">
          {data && (
            <ForceGraph2D
              ref={fgRef}
              graphData={graphData}
              width={size.w}
              height={size.h}
              backgroundColor="#0E1522"
              cooldownTicks={120}
              onEngineStop={() => fgRef.current?.zoomToFit(500, 70)}
              nodeRelSize={5}
              nodeVal={(n: any) => 1 + n.risk * 6}
              nodeColor={(n: any) => riskColor(n.risk)}
              nodeLabel={(n: any) =>
                `${IDENTIFIER_LABEL[n.type] ?? n.type}: ${n.label} · risk ${n.risk}`
              }
              linkColor={() => "#26303F"}
              linkWidth={(l: any) => 0.5 + l.weight * 2}
              onNodeClick={(n: any) => onNodeClick(n as GraphNode)}
              nodeCanvasObjectMode={() => "after"}
              nodeCanvasObject={(node: any, ctx, scale) => {
                // Label only high-risk nodes to keep the canvas readable.
                if (node.risk < 0.7 || scale < 1.2) return;
                const label = node.label;
                ctx.font = `${11 / scale}px Inter, sans-serif`;
                ctx.fillStyle = "#E6EAF2";
                ctx.textAlign = "center";
                ctx.fillText(label, node.x, node.y + 12 / scale);
              }}
            />
          )}
          {!data && (
            <div className="flex h-full items-center justify-center text-sm text-authority-muted">
              Loading network…
            </div>
          )}
        </div>

        {detail && (
          <NodePanel detail={detail} onClose={() => setDetail(null)} />
        )}
      </div>
    </div>
  );
}

function Legend() {
  const items = [
    { c: "#FF4D4D", l: "Critical ≥ 0.85" },
    { c: "#E0A020", l: "High ≥ 0.70" },
    { c: "#22B8CF", l: "Lower" },
  ];
  return (
    <div className="flex gap-3">
      {items.map((it) => (
        <span key={it.l} className="flex items-center gap-1.5 text-xs text-authority-muted">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: it.c }} />
          {it.l}
        </span>
      ))}
    </div>
  );
}

function NodePanel({
  detail,
  onClose,
}: {
  detail: NodeDetail;
  onClose: () => void;
}) {
  const id = detail.identifier;
  return (
    <aside className="absolute right-0 top-0 h-full w-80 overflow-y-auto border-l border-authority-border bg-authority-surface p-4 shadow-xl">
      <div className="mb-3 flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-authority-muted">
            {IDENTIFIER_LABEL[id.type] ?? id.type}
          </p>
          <p className="break-all font-mono text-sm font-semibold">{id.value}</p>
        </div>
        <button onClick={onClose} className="rounded p-1 text-authority-muted hover:text-authority-text" aria-label="Close">
          <X size={16} />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Metric label="Risk" value={id.risk.toFixed(2)} color={riskColor(id.risk)} />
        <Metric label="Reports" value={String(id.reports)} />
      </div>

      <Section title={`Linked identifiers (${detail.linked_identifiers.length})`}>
        {detail.linked_identifiers.length === 0 ? (
          <Empty>No linked identifiers.</Empty>
        ) : (
          <ul className="space-y-1.5">
            {detail.linked_identifiers.map((n) => (
              <li key={n.id} className="flex items-center justify-between gap-2 text-xs">
                <span className="truncate font-mono">{n.value}</span>
                <span
                  className="shrink-0 rounded px-1.5 py-0.5 font-mono"
                  style={{ background: `${riskColor(n.risk)}22`, color: riskColor(n.risk) }}
                >
                  {n.risk.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={`Reports (${detail.reports.length})`}>
        {detail.reports.length === 0 ? (
          <Empty>No reports reference this identifier.</Empty>
        ) : (
          <ul className="space-y-1.5">
            {detail.reports.map((r) => (
              <li key={r.id} className="rounded-lg bg-authority-base px-2 py-1.5 text-xs">
                <span className="font-medium">
                  {CATEGORY_LABEL[r.scam_category] ?? r.scam_category}
                </span>
                <span className="ml-1 text-authority-muted">· {r.channel}</span>
                <span className="block text-[11px] text-authority-muted">
                  {new Date(r.created_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </aside>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-lg bg-authority-base p-2.5">
      <p className="text-[10px] uppercase text-authority-muted">{label}</p>
      <p className="font-mono text-lg font-bold" style={color ? { color } : undefined}>
        {value}
      </p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-authority-muted">
        {title}
      </h3>
      {children}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-authority-muted">{children}</p>;
}
