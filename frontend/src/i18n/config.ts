// i18next configuration. English is the fallback, so any key missing from a
// machine-translated language falls back to accurate English rather than
// showing a raw key. The selected language persists in localStorage.

import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import { applyLanguageFont } from "./fonts";
import { LANGUAGE_CODES, STORAGE_KEY } from "./languages";

import en from "./locales/en.json";
import hi from "./locales/hi.json";
import bn from "./locales/bn.json";
import te from "./locales/te.json";
import mr from "./locales/mr.json";
import ta from "./locales/ta.json";
import gu from "./locales/gu.json";
import kn from "./locales/kn.json";
import ml from "./locales/ml.json";
import pa from "./locales/pa.json";
import or from "./locales/or.json";
import ur from "./locales/ur.json";

const resources = {
  en: { translation: en },
  hi: { translation: hi },
  bn: { translation: bn },
  te: { translation: te },
  mr: { translation: mr },
  ta: { translation: ta },
  gu: { translation: gu },
  kn: { translation: kn },
  ml: { translation: ml },
  pa: { translation: pa },
  or: { translation: or },
  ur: { translation: ur },
} as const;

function initialLanguage(): string {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && LANGUAGE_CODES.includes(stored)) return stored;
  return "en";
}

const startLang = initialLanguage();

i18next.use(initReactI18next).init({
  resources,
  lng: startLang,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnEmptyString: false, // empty strings fall back to English too
});

// Apply the initial font + direction, and keep them in sync on change.
applyLanguageFont(startLang);
i18next.on("languageChanged", (lng) => {
  localStorage.setItem(STORAGE_KEY, lng);
  applyLanguageFont(lng);
});

export function changeLanguage(code: string): void {
  i18next.changeLanguage(code);
}

export default i18next;
