// Holds the most recent detection outcome so the report form can pre-fill
// from a call or a Fraud Shield check (demo flow step 4).

import { create } from "zustand";
import type { ScamCategory, Source } from "../api/types";

export interface LastDetection {
  sessionId: number | null;
  channel: "call" | "sms" | "whatsapp";
  category: ScamCategory;
  content: string;
  redFlags: string[];
  sources: Source[];
  identifiers: string[];
}

interface CallState {
  lastDetection: LastDetection | null;
  setLastDetection: (d: LastDetection) => void;
  clear: () => void;
}

export const useCallStore = create<CallState>((set) => ({
  lastDetection: null,
  setLastDetection: (d) => set({ lastDetection: d }),
  clear: () => set({ lastDetection: null }),
}));
