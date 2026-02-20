import { createContext, useContext, useEffect, useMemo, useState } from "react";
import pretranslated from "./i18nPretranslated.json";

const DEFAULT_LANG = "ja";
const LANGUAGE_STORAGE_KEY = "app_lang";
const SUPPORTED_LANGS = new Set(["ja", "en", "zh-cn", "zh-tw", "ko"]);
const AUTO_TRANSLATE_LANGS = new Set(["zh-cn", "zh-tw", "ko"]);
const RUNTIME_CACHE_KEY = "i18n_runtime_cache_v1";
const runtimeCache = new Map();
const runtimeQueue = new Map();
let runtimeTimer = null;
const runtimeListeners = new Set();
let runtimeInFlight = false;
const publishedDictLoaded = new Set();
const publishedDictInFlight = new Set();

function readRuntimeCache() {
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(RUNTIME_CACHE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return;
    for (const [lang, byText] of Object.entries(parsed)) {
      if (!SUPPORTED_LANGS.has(lang)) continue;
      if (!byText || typeof byText !== "object") continue;
      const map = runtimeCache.get(lang) || new Map();
      for (const [src, tr] of Object.entries(byText)) {
        if (!src) continue;
        map.set(src, String(tr || ""));
      }
      runtimeCache.set(lang, map);
    }
  } catch {
    // ignore cache parse errors
  }
}

function persistRuntimeCache() {
  if (typeof window === "undefined") return;
  try {
    const payload = {};
    for (const [lang, map] of runtimeCache.entries()) {
      payload[lang] = Object.fromEntries(map.entries());
    }
    localStorage.setItem(RUNTIME_CACHE_KEY, JSON.stringify(payload));
  } catch {
    // ignore storage errors
  }
}

function notifyRuntimeUpdated() {
  runtimeListeners.forEach((fn) => {
    try {
      fn();
    } catch {
      // ignore listener errors
    }
  });
}

async function flushRuntimeQueue() {
  if (runtimeInFlight) return;
  const targets = [];
  for (const [queueKey, set] of runtimeQueue.entries()) {
    const [lang, sourceLang] = String(queueKey).split("|");
    const texts = Array.from(set || []).filter(Boolean);
    if (!texts.length) continue;
    runtimeQueue.set(queueKey, new Set());
    targets.push({ lang, sourceLang, texts: texts.slice(0, 150) });
  }
  if (!targets.length) return;

  runtimeInFlight = true;
  try {
    await Promise.all(
      targets.map(async ({ lang, sourceLang, texts }) => {
        const res = await fetch("/api/i18n/translate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_lang: sourceLang || "ja",
            target_lang: lang,
            texts,
          }),
        });
        if (!res.ok) return;
        const data = await res.json().catch(() => null);
        const items = data?.items;
        if (!items || typeof items !== "object") return;
        const byLang = runtimeCache.get(lang) || new Map();
        for (const [src, tr] of Object.entries(items)) {
          if (!src) continue;
          byLang.set(src, String(tr || src));
        }
        runtimeCache.set(lang, byLang);
      })
    );
    persistRuntimeCache();
    notifyRuntimeUpdated();
  } catch {
    // ignore network/runtime translation errors
  } finally {
    runtimeInFlight = false;
    // If new items were queued while in flight, flush again.
    const hasPending = Array.from(runtimeQueue.values()).some((s) => s && s.size > 0);
    if (hasPending) {
      if (runtimeTimer) clearTimeout(runtimeTimer);
      runtimeTimer = setTimeout(() => {
        runtimeTimer = null;
        flushRuntimeQueue();
      }, 120);
    }
  }
}

function enqueueRuntimeTranslation(lang, sourceText, sourceLang = "ja") {
  if (!AUTO_TRANSLATE_LANGS.has(lang)) return;
  if (!sourceText) return;
  const byLang = runtimeCache.get(lang);
  if (byLang && byLang.has(sourceText)) return;
  const queueKey = `${lang}|${sourceLang}`;
  const q = runtimeQueue.get(queueKey) || new Set();
  q.add(sourceText);
  runtimeQueue.set(queueKey, q);
  if (runtimeTimer) return;
  runtimeTimer = setTimeout(() => {
    runtimeTimer = null;
    flushRuntimeQueue();
  }, 120);
}

async function requestPublishedDictionary(lang) {
  if (!AUTO_TRANSLATE_LANGS.has(lang)) return;
  if (publishedDictLoaded.has(lang) || publishedDictInFlight.has(lang)) return;
  publishedDictInFlight.add(lang);
  try {
    const res = await fetch(`/api/i18n/dictionary/${encodeURIComponent(lang)}`);
    if (!res.ok) return;
    const data = await res.json().catch(() => null);
    const items = data?.items;
    if (!items || typeof items !== "object") return;
    const byLang = runtimeCache.get(lang) || new Map();
    for (const [src, tr] of Object.entries(items)) {
      const source = String(src || "").trim();
      const translated = String(tr || "").trim();
      if (!source || !translated) continue;
      byLang.set(source, translated);
    }
    runtimeCache.set(lang, byLang);
    persistRuntimeCache();
    notifyRuntimeUpdated();
    publishedDictLoaded.add(lang);
  } catch {
    // ignore dictionary fetch errors
  } finally {
    publishedDictInFlight.delete(lang);
  }
}

readRuntimeCache();

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
  if (SUPPORTED_LANGS.has(stored)) return stored;
  const browser = (navigator?.language || "").toLowerCase();
  if (browser.startsWith("zh-cn") || browser.startsWith("zh-hans")) return "zh-cn";
  if (browser.startsWith("zh-tw") || browser.startsWith("zh-hant")) return "zh-tw";
  if (browser.startsWith("ko")) return "ko";
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
  let text = value[lang];
  if (!text && AUTO_TRANSLATE_LANGS.has(lang)) {
    requestPublishedDictionary(lang);
    const source = (value.ja || value.en || "").trim();
    if (source) {
      const byLang = runtimeCache.get(lang);
      const translated = byLang?.get(source);
      if (translated) {
        text = translated;
      }
      if (!text) {
        const pre = pretranslated?.[lang]?.[source];
        if (pre) {
          text = pre;
        }
      }
      if (!text) {
        const sourceLang = value.ja ? "ja" : "en";
        enqueueRuntimeTranslation(lang, source, sourceLang);
        text = source;
      }
    }
  }
  if (!text) text = value.en || value.ja || "";
  return interpolate(text, vars);
}

export function getStoredLanguage() {
  return resolveStoredLang();
}

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(resolveStoredLang);
  const [, setRuntimeRevision] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
    } catch {
      // ignore storage errors
    }
    if (document?.documentElement) {
      document.documentElement.lang = lang;
    }
  }, [lang]);

  useEffect(() => {
    if (AUTO_TRANSLATE_LANGS.has(lang)) {
      requestPublishedDictionary(lang);
    }
  }, [lang]);

  useEffect(() => {
    const onUpdate = () => setRuntimeRevision((v) => v + 1);
    runtimeListeners.add(onUpdate);
    return () => {
      runtimeListeners.delete(onUpdate);
    };
  }, []);

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
