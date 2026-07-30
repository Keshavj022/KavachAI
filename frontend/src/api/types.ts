// Shared API types mirroring the backend Pydantic schemas.

export type Role = "citizen" | "authority";

export type Verdict = "safe" | "suspicious" | "scam";

export type ScamStage =
  | "none"
  | "authority_claim"
  | "accusation"
  | "isolation"
  | "money_demand";

export type ScamCategory =
  | "digital_arrest"
  | "kyc_update"
  | "investment"
  | "fake_delivery"
  | "refund"
  | "loan"
  | "other";

export type IdentifierType = "phone" | "upi" | "account" | "url" | "device";

export type Channel = "call" | "sms" | "whatsapp";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: Role;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  preferred_language: string;
  created_at: string;
}

export interface Source {
  title: string;
  snippet: string;
  ref: string;
}

export interface VerdictOut {
  verdict: Verdict;
  confidence: number;
  category: ScamCategory;
  red_flags: string[];
  explanation: string;
  sources: Source[];
  known_scammer: boolean;
  stage: ScamStage;
}

// Server -> client frame on the live-call websocket.
export interface WSMessage {
  partial_transcript: string;
  stage: ScamStage;
  confidence: number;
  verdict: Verdict;
  interrupt: boolean;
  warn: boolean;
  explanation: string | null;
  red_flags: string[];
  sources: Source[];
  known_scammer: boolean;
  detector: string; // "groq" | "fallback"
  done: boolean;
}

export interface TrustedContact {
  id: number;
  name: string;
  phone: string;
}

export interface Report {
  id: number;
  channel: Channel;
  scam_category: ScamCategory;
  content: string;
  status: "filed" | "under_review" | "actioned";
  created_at: string;
  location_lat: number | null;
  location_lng: number | null;
  location_label: string | null;
  identifiers: IdentifierBrief[];
  reporter_name?: string;
  alerts_sent?: number;
}

export interface IdentifierBrief {
  id: number;
  type: IdentifierType;
  value: string;
  risk_score: number;
  report_count: number;
}

export interface GraphNode {
  id: number;
  label: string;
  type: IdentifierType;
  risk: number;
  reports: number;
  ring: number;
}

export interface GraphLink {
  source: number;
  target: number;
  weight: number;
  reason: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}
