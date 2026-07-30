// Types for the decoy WebSocket stream and live view.

export type ScamStage =
  | "none"
  | "authority_claim"
  | "accusation"
  | "isolation"
  | "money_demand";

export type AgentMode = "monitor" | "stall" | "wrap_up";

export interface DecoyIdentifier {
  type: string; // phone | upi | account | ifsc | amount | agency | officer | station | fir | url
  value: string;
  label: string;
}

export interface TranscriptTurn {
  speaker: "scammer" | "agent";
  text: string;
  language: string;
}

// One spoken line: text + the language + its synthesized voice clip (or null
// when the TTS model is not loaded, in which case the client paces from text).
export interface SpokenLine {
  text: string;
  language: string;
  audio_url: string | null;
}

// Detection state that lands as the caller's line is heard (drives the meter,
// the mode badge and the identifier chips).
export interface DecoyDetection {
  scam_prob: number;
  stage: ScamStage;
  scam_type: string;
  red_flags: string[];
  new_identifiers: DecoyIdentifier[];
  identifiers_total: number;
  known_ring_hit: boolean;
}

// Server → client WebSocket frames.
//
// A `turn` bundles one full exchange — the caller's line, the detection it
// produced, the agent mode, and Ramesh's reply — each with its voice clip. The
// client plays them back in order so text and audio stay in lockstep.
export type DecoyFrame =
  | {
      type: "turn";
      // A turn is streamed as two frames: a caller frame (scammer + detection,
      // agent null) and a decoy frame (agent, scammer + detection null). The
      // opening greeting is a decoy frame with no caller. The frontend queue
      // plays whichever half is present, in order.
      scammer: SpokenLine | null;
      detection: DecoyDetection | null;
      mode: AgentMode;
      agent: (SpokenLine & { used_fallback: boolean }) | null;
    }
  | {
      type: "call_ended";
      verdict: "scam" | "safe";
      package_id?: string;
      duration_seconds: number;
      identifiers_total: number;
      time_to_first_identifier: number | null;
    }
  | { type: "error"; detail: string };
