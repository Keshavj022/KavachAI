// Display formatting helpers shared across authority views.

export const CATEGORY_LABEL: Record<string, string> = {
  digital_arrest: "Digital arrest",
  kyc_update: "KYC update",
  investment: "Investment",
  fake_delivery: "Fake delivery",
  refund: "Refund",
  loan: "Loan",
  other: "Other",
};

export const IDENTIFIER_LABEL: Record<string, string> = {
  phone: "Phone",
  upi: "UPI",
  account: "Account",
  url: "URL",
  device: "Device",
};

export function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

// Node/edge colour by risk — shared by the graph. Colour-blind-safe ramp.
export function riskColor(risk: number): string {
  if (risk >= 0.85) return "#FF4D4D";
  if (risk >= 0.7) return "#E0A020";
  if (risk >= 0.4) return "#C9A227";
  return "#22B8CF";
}
