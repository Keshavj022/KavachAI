/**
 * Original SVG character illustrations for the Stay Safe guide. Flat, warm, and
 * distinctly Indian (skin tones, kurta, salwar, glasses). Not clipart — drawn
 * here so they can be recoloured and animated freely. Attribution: original
 * artwork for Kavach.
 */

type Emotion = "relaxed" | "frightened" | "isolated" | "determined" | "relieved";

const SKIN = "#C88A5A";
const SKIN_SHADE = "#B4784A";

/** Raju uncle — 68, grey hair, reading glasses, cream kurta. */
export function RajuUncle({
  emotion = "relaxed",
  size = 160,
}: {
  emotion?: Emotion;
  size?: number;
}) {
  // Mouth + brow paths convey the emotion.
  const mouth: Record<Emotion, string> = {
    relaxed: "M 66 92 Q 80 100 94 92",
    frightened: "M 68 96 Q 80 88 92 96",
    isolated: "M 68 96 L 92 96",
    determined: "M 66 93 L 94 93",
    relieved: "M 66 91 Q 80 101 94 91",
  };
  const browY = emotion === "frightened" ? 60 : 64;
  return (
    <svg viewBox="0 0 160 200" width={size} height={size * 1.25} role="img"
         aria-label="Raju uncle">
      {/* kurta */}
      <path d="M 40 200 Q 40 140 80 140 Q 120 140 120 200 Z" fill="#EFE6D2" />
      <path d="M 80 140 L 80 200" stroke="#D8CBB0" strokeWidth="2" />
      <circle cx="80" cy="150" r="2.5" fill="#B9A97F" />
      {/* neck */}
      <rect x="70" y="120" width="20" height="26" rx="8" fill={SKIN_SHADE} />
      {/* head */}
      <circle cx="80" cy="86" r="40" fill={SKIN} />
      <path d="M 44 78 Q 42 44 80 44 Q 118 44 116 78 Q 110 60 80 58 Q 50 60 44 78 Z"
            fill="#C9CCD1" />
      {/* ears */}
      <circle cx="42" cy="88" r="7" fill={SKIN} />
      <circle cx="118" cy="88" r="7" fill={SKIN} />
      {/* glasses */}
      <circle cx="66" cy="82" r="12" fill="none" stroke="#3A3A3A" strokeWidth="2.5" />
      <circle cx="94" cy="82" r="12" fill="none" stroke="#3A3A3A" strokeWidth="2.5" />
      <line x1="78" y1="82" x2="82" y2="82" stroke="#3A3A3A" strokeWidth="2.5" />
      {/* eyes */}
      <circle cx="66" cy="82" r="3" fill="#2A2A2A" />
      <circle cx="94" cy="82" r="3" fill="#2A2A2A" />
      {/* brows */}
      <path d={`M 56 ${browY} L 74 ${browY - 2}`} stroke="#8A8D93" strokeWidth="2.5" strokeLinecap="round" />
      <path d={`M 86 ${browY - 2} L 104 ${browY}`} stroke="#8A8D93" strokeWidth="2.5" strokeLinecap="round" />
      {/* moustache + mouth */}
      <path d="M 68 100 Q 80 104 92 100" stroke="#9A9DA2" strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d={mouth[emotion]} stroke="#7A4A38" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      {emotion === "isolated" && (
        <g>
          <circle cx="80" cy="100" r="72" fill="none" stroke="#D12E2E" strokeWidth="3" strokeDasharray="6 6" opacity="0.7" />
          <rect x="72" y="14" width="16" height="14" rx="3" fill="#D12E2E" />
          <path d="M 75 14 v -3 a 5 5 0 0 1 10 0 v 3" fill="none" stroke="#D12E2E" strokeWidth="2.5" />
        </g>
      )}
    </svg>
  );
}

/** Priya — lawyer, calm and professional, teal salwar, holds a document. */
export function Priya({ size = 150 }: { size?: number }) {
  return (
    <svg viewBox="0 0 160 200" width={size} height={size * 1.25} role="img" aria-label="Priya">
      <path d="M 42 200 Q 42 138 80 138 Q 118 138 118 200 Z" fill="#0B6E7A" />
      <path d="M 80 138 L 80 200" stroke="#095059" strokeWidth="2" />
      <rect x="70" y="120" width="20" height="24" rx="8" fill={SKIN_SHADE} />
      {/* hair back */}
      <path d="M 40 92 Q 38 46 80 44 Q 122 46 120 92 L 120 128 Q 110 118 110 96 L 50 96 Q 50 118 40 128 Z" fill="#2B2320" />
      <circle cx="80" cy="84" r="38" fill={SKIN} />
      {/* bindi */}
      <circle cx="80" cy="58" r="2.5" fill="#C4161C" />
      <circle cx="41" cy="86" r="6" fill={SKIN} />
      <circle cx="119" cy="86" r="6" fill={SKIN} />
      {/* eyes + confident brows */}
      <circle cx="67" cy="82" r="3.2" fill="#2A2A2A" />
      <circle cx="93" cy="82" r="3.2" fill="#2A2A2A" />
      <path d="M 58 74 L 74 74" stroke="#2B2320" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M 86 74 L 102 74" stroke="#2B2320" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M 70 96 Q 80 102 90 96" stroke="#7A4A38" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      {/* document */}
      <rect x="96" y="150" width="34" height="26" rx="3" fill="#FFFFFF" transform="rotate(-8 113 163)" />
      <line x1="102" y1="158" x2="124" y2="156" stroke="#8A97AC" strokeWidth="2" transform="rotate(-8 113 163)" />
      <line x1="102" y1="164" x2="124" y2="162" stroke="#8A97AC" strokeWidth="2" transform="rotate(-8 113 163)" />
    </svg>
  );
}

/** Inspector Sharma — the scammer, muted/dark, fake uniform + cap. `shrink`
 *  progressively reduces him as the victim learns their rights. */
export function Scammer({ size = 140, shrink = 1 }: { size?: number; shrink?: number }) {
  return (
    <svg viewBox="0 0 160 200" width={size * shrink} height={size * 1.25 * shrink}
         role="img" aria-label="Inspector Sharma (impersonator)" style={{ transition: "all 300ms" }}>
      <path d="M 44 200 Q 44 140 80 140 Q 116 140 116 200 Z" fill="#2C3444" />
      <path d="M 62 140 L 66 200 M 98 140 L 94 200" stroke="#3A4456" strokeWidth="2" />
      {/* fake badge */}
      <circle cx="64" cy="158" r="5" fill="#8A6D2F" />
      <rect x="70" y="120" width="20" height="24" rx="8" fill={SKIN_SHADE} />
      <circle cx="80" cy="86" r="38" fill={SKIN} />
      {/* cap */}
      <path d="M 42 74 Q 44 50 80 50 Q 116 50 118 74 Z" fill="#1E2734" />
      <rect x="40" y="72" width="80" height="8" rx="3" fill="#141A22" />
      <rect x="72" y="58" width="16" height="10" rx="2" fill="#8A6D2F" />
      {/* stern eyes/brows */}
      <path d="M 58 78 L 74 82" stroke="#1E2734" strokeWidth="3" strokeLinecap="round" />
      <path d="M 86 82 L 102 78" stroke="#1E2734" strokeWidth="3" strokeLinecap="round" />
      <circle cx="67" cy="86" r="3" fill="#2A2A2A" />
      <circle cx="93" cy="86" r="3" fill="#2A2A2A" />
      <path d="M 70 104 L 90 104" stroke="#5A3A2E" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

/** Raju uncle's son — 35-40, worried but capable, casual shirt + phone. */
export function Son({ size = 130 }: { size?: number }) {
  return (
    <svg viewBox="0 0 160 200" width={size} height={size * 1.25} role="img" aria-label="Son">
      <path d="M 44 200 Q 44 140 80 140 Q 116 140 116 200 Z" fill="#22808A" />
      <rect x="70" y="122" width="20" height="22" rx="8" fill={SKIN_SHADE} />
      <circle cx="80" cy="88" r="36" fill={SKIN} />
      <path d="M 46 82 Q 46 52 80 52 Q 114 52 114 82 Q 108 66 80 66 Q 52 66 46 82 Z" fill="#241E1B" />
      <circle cx="68" cy="86" r="3" fill="#2A2A2A" />
      <circle cx="92" cy="86" r="3" fill="#2A2A2A" />
      <path d="M 60 78 L 74 78 M 86 78 L 100 78" stroke="#241E1B" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M 70 100 Q 80 104 90 100" stroke="#7A4A38" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      {/* phone in hand */}
      <rect x="98" y="150" width="16" height="28" rx="3" fill="#141A22" transform="rotate(12 106 164)" />
      <rect x="100" y="154" width="12" height="20" rx="1" fill="#22B8CF" transform="rotate(12 106 164)" opacity="0.7" />
    </svg>
  );
}
