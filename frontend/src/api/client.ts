// Typed fetch wrapper. Attaches the bearer token, centralises base URLs and
// surfaces backend error details as thrown Error messages the UI can show.

import type {
  GraphData,
  Report,
  TokenResponse,
  TrustedContact,
  User,
  VerdictOut,
} from "./types";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const WS_BASE =
  import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000";

const TOKEN_KEY = "kavach_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: URLSearchParams;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.auth !== false) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let body: BodyInit | undefined;
  if (opts.form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = opts.form.toString();
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // --- Auth ---
  login(email: string, password: string): Promise<TokenResponse> {
    const form = new URLSearchParams({ username: email, password });
    return request<TokenResponse>("/api/auth/login", {
      method: "POST",
      form,
      auth: false,
    });
  },
  register(payload: {
    email: string;
    password: string;
    full_name: string;
    role: "citizen" | "authority";
  }): Promise<TokenResponse> {
    return request<TokenResponse>("/api/auth/register", {
      method: "POST",
      body: payload,
      auth: false,
    });
  },
  me(): Promise<User> {
    return request<User>("/api/auth/me");
  },

  // --- Detection ---
  checkMessage(content: string, channel: string): Promise<VerdictOut> {
    return request<VerdictOut>("/api/detect/message", {
      method: "POST",
      body: { content, channel },
    });
  },
  lookupIdentifier(value: string): Promise<VerdictOut> {
    return request<VerdictOut>(
      `/api/identifier/lookup?value=${encodeURIComponent(value)}`,
    );
  },

  // --- Call sessions ---
  startCall(): Promise<{ session_id: number; demo_scripts: string[] }> {
    return request("/api/call/start", { method: "POST" });
  },
  endCall(id: number): Promise<Record<string, unknown>> {
    return request(`/api/call/${id}/end`, { method: "POST" });
  },

  // --- Reports ---
  listReports(): Promise<Report[]> {
    return request<Report[]>("/api/reports");
  },
  getReport(id: number): Promise<Report> {
    return request<Report>(`/api/reports/${id}`);
  },
  createReport(payload: {
    call_session_id?: number | null;
    channel: string;
    scam_category: string;
    content: string;
    location_label?: string | null;
    location_lat?: number | null;
    location_lng?: number | null;
    identifier_values?: string[];
    notify_contacts?: boolean;
  }): Promise<Report> {
    return request<Report>("/api/reports", { method: "POST", body: payload });
  },

  // --- Contacts ---
  listContacts(): Promise<TrustedContact[]> {
    return request<TrustedContact[]>("/api/contacts");
  },
  addContact(name: string, phone: string): Promise<TrustedContact> {
    return request<TrustedContact>("/api/contacts", {
      method: "POST",
      body: { name, phone },
    });
  },
  deleteContact(id: number): Promise<void> {
    return request<void>(`/api/contacts/${id}`, { method: "DELETE" });
  },

  // --- Graph / authority intelligence ---
  graph(): Promise<GraphData> {
    return request<GraphData>("/api/graph");
  },
  graphNode(id: number): Promise<NodeDetail> {
    return request<NodeDetail>(`/api/graph/node/${id}`);
  },
  stats(): Promise<StatsData> {
    return request<StatsData>("/api/authority/stats");
  },

  // --- Evidence (authority only) ---
  evidence(reportId: number): Promise<{ items: EvidenceMeta[] }> {
    return request<{ items: EvidenceMeta[] }>(`/api/evidence/${reportId}`);
  },

  // --- Citizen guide ---
  guideContacts(lang: string): Promise<GuideContacts> {
    return request<GuideContacts>(`/api/guide/contacts?lang=${encodeURIComponent(lang)}`);
  },

  // --- Decoy agent ---
  startDecoy(language: string, scenario: string, demoMode = true): Promise<DecoyStart> {
    return request<DecoyStart>("/api/decoy/session/start", {
      method: "POST",
      body: { language, scenario, demo_mode: demoMode },
    });
  },
  getDecoyPackage(packageId: string): Promise<DecoyPackage> {
    return request<DecoyPackage>(`/api/decoy/package/${packageId}`);
  },
  submitDecoyPackage(
    packageId: string,
    channel: string,
  ): Promise<{ submission_id: string; status: string; channel: string }> {
    return request(`/api/decoy/package/${packageId}/submit?channel=${channel}`, {
      method: "POST",
    });
  },
};

export interface GuideContacts {
  lang: string;
  helplines: { name: string; number: string; description: string; tel_link: string }[];
  bank_fraud_helplines: { name: string; number: string; tel_link: string }[];
  portals: { name: string; url: string; description: string }[];
  legal_sections: { section: string; act: string; summary: string }[];
}

export interface DecoyStart {
  session_id: number;
  greeting_text: string;
  persona_intro_audio_url: string | null;
  demo_scripts: string[];
}

export interface DecoyAmount {
  raw: string;
  value_inr: number | null;
}

export interface DecoyPackage {
  package_id: string;
  generated_at: string;
  call_duration_seconds: number;
  language_detected: string;
  scam_type: string;
  confidence: number;
  stage_at_wrap_up: string;
  transcript: string;
  identifiers: {
    phones: string[];
    upis: string[];
    accounts: string[];
    ifsc: string[];
    urls: string[];
  };
  amounts_demanded: DecoyAmount[];
  agency_claimed: string[];
  officer_name_claimed: string[];
  station_claimed: string[];
  fir_number_claimed: string[];
  red_flags: string[];
  audio_sha256: string;
  ring_id: string | null;
  prior_report_count: number;
  estimated_victims: number;
  fir_narrative: string;
  submission_id: string | null;
  submission_status: string | null;
}

export interface EvidenceMeta {
  id: number;
  sha256_hash: string;
  created_at: string;
  preview: string | null;
}

export interface NodeDetail {
  identifier: {
    id: number;
    type: string;
    value: string;
    risk: number;
    reports: number;
    first_seen: string;
  };
  linked_identifiers: { id: number; type: string; value: string; risk: number }[];
  reports: {
    id: number;
    scam_category: string;
    channel: string;
    created_at: string;
    status: string;
  }[];
}

export interface StatsData {
  total_reports: number;
  total_identifiers: number;
  high_risk_identifiers: number;
  active_rings: number;
  categories: { category: string; count: number }[];
  trend: { date: string; count: number }[];
  top_rings: {
    ring: number;
    size: number;
    peak_risk: number;
    total_reports: number;
    types: string[];
  }[];
}
