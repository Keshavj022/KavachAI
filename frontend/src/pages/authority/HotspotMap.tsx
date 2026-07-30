import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { api } from "../../api/client";
import type { Report } from "../../api/types";
import { CATEGORY_LABEL } from "./format";

// Category → marker colour. CircleMarker avoids the Leaflet default-icon
// bundler issue entirely (no image assets needed).
const CATEGORY_COLOR: Record<string, string> = {
  digital_arrest: "#FF4D4D",
  kyc_update: "#E0A020",
  investment: "#22B8CF",
  fake_delivery: "#9B8CFF",
  refund: "#4DD4AC",
  loan: "#E06CB0",
  other: "#8A97AC",
};

export default function HotspotMap() {
  const [reports, setReports] = useState<Report[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listReports()
      .then(setReports)
      .catch(() => setError("Could not load map data."));
  }, []);

  const located = useMemo(
    () => reports.filter((r) => r.location_lat != null && r.location_lng != null),
    [reports],
  );

  if (error) return <p className="text-authority-red">{error}</p>;

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <div className="mb-3">
        <h1 className="font-display text-2xl font-bold">Hotspot map</h1>
        <p className="text-sm text-authority-muted">
          Geographic distribution of reported fraud ({located.length} located).
        </p>
      </div>

      <div className="flex-1 overflow-hidden rounded-xl border border-authority-border">
        <MapContainer
          center={[22.5, 79]}
          zoom={5}
          scrollWheelZoom
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {located.map((r) => {
            const color = CATEGORY_COLOR[r.scam_category] ?? "#8A97AC";
            return (
              <CircleMarker
                key={r.id}
                center={[r.location_lat as number, r.location_lng as number]}
                radius={9}
                pathOptions={{
                  color,
                  fillColor: color,
                  fillOpacity: 0.55,
                  weight: 2,
                }}
              >
                <Popup>
                  <div className="text-sm">
                    <p className="font-semibold">
                      {CATEGORY_LABEL[r.scam_category] ?? r.scam_category}
                    </p>
                    <p>{r.location_label}</p>
                    <p className="text-xs text-gray-500">
                      {new Date(r.created_at).toLocaleDateString()} · {r.channel}
                    </p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap gap-3">
        {Object.entries(CATEGORY_LABEL).map(([key, label]) => (
          <span key={key} className="flex items-center gap-1.5 text-xs text-authority-muted">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: CATEGORY_COLOR[key] }}
            />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
