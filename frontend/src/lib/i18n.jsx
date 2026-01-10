import { createContext, useContext, useEffect, useMemo, useState } from "react";

const DEFAULT_LANG = "ja";
const LANGUAGE_STORAGE_KEY = "app_lang";

const LanguageContext = createContext({
  lang: DEFAULT_LANG,
  setLang: () => {},
  t: (value, vars) => {
    if (typeof value === "string") return value;
    if (!value) return "";
    const text = value[DEFAULT_LANG] || value.en || "";
    return interpolate(text, vars);
  },
});

function resolveStoredLang() {
  if (typeof window === "undefined") return DEFAULT_LANG;
  const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
  if (stored === "ja" || stored === "en") return stored;
  const browser = (navigator?.language || "").toLowerCase();
  return browser.startsWith("en") ? "en" : DEFAULT_LANG;
}

function interpolate(text, vars) {
  if (!vars) return text;
  return text.replace(/\{\{(\w+)\}\}/g, (_, key) => {
    const value = vars[key];
    return value === undefined || value === null ? "" : String(value);
  });
}

export function translate(value, lang, vars) {
  if (typeof value === "string") {
    return interpolate(value, vars);
  }
  if (!value || typeof value !== "object") return "";
  const text = value[lang] || value.ja || value.en || "";
  return interpolate(text, vars);
}

export function getStoredLanguage() {
  return resolveStoredLang();
}

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(resolveStoredLang);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
    } catch {
      // ignore storage errors
    }
    if (document?.documentElement) {
      document.documentElement.lang = lang === "en" ? "en" : "ja";
    }
  }, [lang]);

  const value = useMemo(() => {
    return {
      lang,
      setLang,
      t: (value, vars) => translate(value, lang, vars),
    };
  }, [lang]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useI18n() {
  return useContext(LanguageContext);
}
