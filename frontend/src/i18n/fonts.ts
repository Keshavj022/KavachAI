// Lazy Noto font loading. The base bundle ships Latin + a light Noto Sans; the
// per-script Noto family for a language is only fetched from Google Fonts when
// that language is first selected, keeping the initial load lean.

import { languageMeta } from "./languages";

const loaded = new Set<string>();

/** Ensure the Noto font for a language is loaded, and set the document's
 *  active font-family variable + direction. */
export function applyLanguageFont(code: string): void {
  const meta = languageMeta(code);

  if (meta.notoFamily && !loaded.has(meta.notoFamily)) {
    loaded.add(meta.notoFamily);
    const family = meta.notoFamily.replace(/ /g, "+");
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${family}:wght@400;500;600;700&display=swap`;
    document.head.appendChild(link);
  }

  // Expose the active script font as a CSS variable the app can prepend to its
  // font stack, so Indic text renders in the correct Noto face.
  const root = document.documentElement;
  root.style.setProperty(
    "--script-font",
    meta.notoFamily ? `"${meta.notoFamily}", ` : "",
  );
  root.setAttribute("dir", meta.dir);
  root.setAttribute("lang", code);
}
