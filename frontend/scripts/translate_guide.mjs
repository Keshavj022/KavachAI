/**
 * Fill the machine-translated locale files using the LOCAL Ollama model.
 *
 * English (en.json) and Hindi (hi.json) are hand-written and reviewed; this
 * script generates the other ten languages from the English base, preserving
 * proper nouns, numbers, helpline numbers, URLs and legal citations verbatim,
 * per the brief. Run it with Ollama running locally:
 *
 *   node scripts/translate_guide.mjs                # all 10 languages
 *   node scripts/translate_guide.mjs ta te          # only these
 *
 * Each produced file keeps its `_meta`/`_note` and merges the translated keys.
 * A professional review is recommended before production (the `_note` says so).
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LOCALES = path.join(__dirname, "..", "src", "i18n", "locales");
const OLLAMA = process.env.OLLAMA_BASE_URL ?? "http://localhost:11434";
const MODEL = process.env.OLLAMA_MODEL ?? "gemma3:4b";

const TARGET_NAMES = {
  bn: "Bengali", te: "Telugu", mr: "Marathi", ta: "Tamil", gu: "Gujarati",
  kn: "Kannada", ml: "Malayalam", pa: "Punjabi", or: "Odia", ur: "Urdu",
};

const PROMPT = (lang, text) =>
  `You are a professional translator. Translate the following text into ${lang}. ` +
  `The audience is ordinary Indian citizens, including older adults. Use respectful, ` +
  `simple, spoken language — not formal or bureaucratic. Preserve all proper nouns, ` +
  `numbers, helpline numbers, URLs, and legal section citations exactly as they appear ` +
  `(e.g. "1930", "cybercrime.gov.in", "Section 66D", "BNS 2023" — do not translate these). ` +
  `Keep the emotional tone: reassuring, clear, direct. Return ONLY the translation, no quotes.\n\n` +
  `Text to translate:\n${text}`;

// Flatten/unflatten nested string maps (skip keys starting with "_").
function flatten(obj, prefix = "", out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    if (k.startsWith("_")) continue;
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "string") out[key] = v;
    else if (Array.isArray(v)) v.forEach((s, i) => (out[`${key}.${i}`] = s));
    else if (v && typeof v === "object") flatten(v, key, out);
  }
  return out;
}
function setDeep(obj, dotted, value) {
  const parts = dotted.split(".");
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i];
    const nextIsIndex = /^\d+$/.test(parts[i + 1]);
    if (cur[p] == null) cur[p] = nextIsIndex ? [] : {};
    cur = cur[p];
  }
  cur[parts[parts.length - 1]] = value;
}

async function translate(lang, text) {
  const res = await fetch(`${OLLAMA}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: MODEL, prompt: PROMPT(lang, text), stream: false,
      options: { temperature: 0.2, num_predict: 400 },
    }),
  });
  if (!res.ok) throw new Error(`Ollama ${res.status}`);
  return (await res.json()).response.trim();
}

async function run() {
  const en = JSON.parse(fs.readFileSync(path.join(LOCALES, "en.json"), "utf8"));
  const flat = flatten(en);
  const codes = process.argv.slice(2).length
    ? process.argv.slice(2)
    : Object.keys(TARGET_NAMES);

  for (const code of codes) {
    const langName = TARGET_NAMES[code];
    if (!langName) { console.warn(`skip unknown ${code}`); continue; }
    const file = path.join(LOCALES, `${code}.json`);
    const existing = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : {};
    const out = { _meta: existing._meta, _note: existing._note };

    console.log(`\n== ${code} (${langName}) — ${Object.keys(flat).length} strings ==`);
    let n = 0;
    for (const [key, value] of Object.entries(flat)) {
      try {
        const t = await translate(langName, value);
        setDeep(out, key, t);
      } catch (e) {
        setDeep(out, key, value); // fall back to English on failure
        console.warn(`  ${key}: ${e.message} (kept English)`);
      }
      if (++n % 20 === 0) console.log(`  ${n}/${Object.keys(flat).length}`);
    }
    fs.writeFileSync(file, JSON.stringify(out, null, 2) + "\n");
    console.log(`  wrote ${code}.json`);
  }
}

run().catch((e) => { console.error(e); process.exit(1); });
