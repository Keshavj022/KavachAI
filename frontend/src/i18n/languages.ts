// The 12 supported languages, their native names, scripts, direction, and the
// Noto font family that renders each script correctly. Fonts are lazy-loaded
// (see fonts.ts) so the base bundle stays lean.

export interface LanguageMeta {
  code: string;
  nativeName: string;
  englishName: string;
  dir: "ltr" | "rtl";
  // Google-Fonts Noto family that covers this language's script.
  notoFamily: string | null; // null → Latin, covered by the base fonts
}

export const LANGUAGES: LanguageMeta[] = [
  { code: "en", nativeName: "English", englishName: "English", dir: "ltr", notoFamily: null },
  { code: "hi", nativeName: "हिंदी", englishName: "Hindi", dir: "ltr", notoFamily: "Noto Sans Devanagari" },
  { code: "bn", nativeName: "বাংলা", englishName: "Bengali", dir: "ltr", notoFamily: "Noto Sans Bengali" },
  { code: "te", nativeName: "తెలుగు", englishName: "Telugu", dir: "ltr", notoFamily: "Noto Sans Telugu" },
  { code: "mr", nativeName: "मराठी", englishName: "Marathi", dir: "ltr", notoFamily: "Noto Sans Devanagari" },
  { code: "ta", nativeName: "தமிழ்", englishName: "Tamil", dir: "ltr", notoFamily: "Noto Sans Tamil" },
  { code: "gu", nativeName: "ગુજરાતી", englishName: "Gujarati", dir: "ltr", notoFamily: "Noto Sans Gujarati" },
  { code: "kn", nativeName: "ಕನ್ನಡ", englishName: "Kannada", dir: "ltr", notoFamily: "Noto Sans Kannada" },
  { code: "ml", nativeName: "മലയാളം", englishName: "Malayalam", dir: "ltr", notoFamily: "Noto Sans Malayalam" },
  { code: "pa", nativeName: "ਪੰਜਾਬੀ", englishName: "Punjabi", dir: "ltr", notoFamily: "Noto Sans Gurmukhi" },
  { code: "or", nativeName: "ଓଡ଼ିଆ", englishName: "Odia", dir: "ltr", notoFamily: "Noto Sans Oriya" },
  { code: "ur", nativeName: "اردو", englishName: "Urdu", dir: "rtl", notoFamily: "Noto Nastaliq Urdu" },
];

export const LANGUAGE_CODES = LANGUAGES.map((l) => l.code);
export const STORAGE_KEY = "kavach_language";

export function languageMeta(code: string): LanguageMeta {
  return LANGUAGES.find((l) => l.code === code) ?? LANGUAGES[0];
}
