"use client";

import { useEffect, useState } from "react";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { LanguageProvider } from "./lib/i18n";
import { initTheme } from "./theme";

const SITE_KEY_ENV = (process.env.NEXT_PUBLIC_SITE_KEY || "").toString().trim().toLowerCase();
type SiteKey = "romance" | "history" | "main";

function detectSiteKeyFromHost(): SiteKey {
  if (typeof window === "undefined") return "main";
  const host = (window.location.hostname || "").toLowerCase();
  if (
    host.startsWith("romance.") ||
    host.includes("romance") ||
    host.startsWith("renai.") ||
    host.includes("renai")
  ) {
    return "romance";
  }
  if (
    host.startsWith("history.") ||
    host.includes("history") ||
    host.startsWith("rekishi.") ||
    host.includes("rekishi")
  ) {
    return "history";
  }
  return "main";
}

function normalizeSiteKey(siteKey: string): SiteKey {
  if (siteKey === "romance" || siteKey === "history") return siteKey;
  return "main";
}

function getActiveSiteKey(): SiteKey {
  return normalizeSiteKey(SITE_KEY_ENV || detectSiteKeyFromHost());
}

function applySiteBranding(siteKey: SiteKey) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.siteKey = siteKey;
  const titleBySiteKey: Record<SiteKey, string> = {
    romance: "恋愛小説Lexis（レクシー/レクシス）",
    history: "歴史小説Lexis（レクシー/レクシス）",
    main: "小説投稿サイトLexis（レクシー/レクシス）",
  };
  if (!document.title) {
    document.title = titleBySiteKey[siteKey] || titleBySiteKey.main;
  }
}

function installSiteKeyFetchHeader(siteKey: SiteKey) {
  if (typeof window === "undefined" || typeof window.fetch !== "function") return;
  if (window.__lexisFetchHeaderInstalled) return;
  const originalFetch = window.fetch.bind(window);
  window.__lexisFetchHeaderInstalled = true;
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    let urlText = "";
    if (typeof input === "string") {
      urlText = input;
    } else if (input instanceof Request) {
      urlText = input.url;
    }

    let isApiRequest = false;
    try {
      const resolved = new URL(urlText, window.location.origin);
      isApiRequest = resolved.pathname.startsWith("/api/");
    } catch {
      isApiRequest = false;
    }

    if (!isApiRequest) return originalFetch(input, init);

    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    if (init && init.headers) {
      const extra = new Headers(init.headers);
      extra.forEach((value, key) => headers.set(key, value));
    }
    if (!headers.has("x-site-key")) {
      headers.set("X-Site-Key", siteKey);
    }

    return originalFetch(input, { ...(init || {}), headers });
  };
}

function applyGlobalButtonClasses() {
  if (typeof document === "undefined") return;
  document.querySelectorAll("a:not(.btn-border):not(.text-link), button:not(.btn-border)").forEach((el) => {
    el.classList.add("btn", "btn-border");
  });
}

export default function NextClientApp() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const activeSiteKey = getActiveSiteKey();
    installSiteKeyFetchHeader(activeSiteKey);
    applySiteBranding(activeSiteKey);
    initTheme();
    applyGlobalButtonClasses();
    setMounted(true);

    const observer = new MutationObserver(applyGlobalButtonClasses);
    observer.observe(document.body, { childList: true, subtree: true });

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((e) => {
        console.error("failed to register service worker", e);
      });
    }

    return () => observer.disconnect();
  }, []);

  if (!mounted) return null;

  return (
    <LanguageProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </LanguageProvider>
  );
}
