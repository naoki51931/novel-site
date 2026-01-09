const isBrowser = typeof window !== "undefined";

const pushDataLayer = (payload) => {
  if (!isBrowser) return;
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(payload);
};

const getPagePayload = (overrides = {}) => {
  if (!isBrowser) return { ...overrides };
  return {
    page_path: overrides.page_path ?? window.location.pathname + window.location.search + window.location.hash,
    page_title: overrides.page_title ?? document.title,
    page_location: overrides.page_location ?? window.location.href,
  };
};

export const trackEvent = (eventName, params = {}) => {
  if (!eventName) return;
  const payload = { event: eventName, ...params };
  pushDataLayer(payload);

  if (isBrowser && typeof window.gtag === "function") {
    window.gtag("event", eventName, params);
  }

  if (isBrowser && typeof window.fbq === "function") {
    window.fbq("trackCustom", eventName, params);
  }
};

export const trackPageView = (overrides = {}) => {
  const payload = getPagePayload(overrides);
  pushDataLayer({ event: "page_view", ...payload });

  if (isBrowser && typeof window.gtag === "function") {
    window.gtag("event", "page_view", payload);
  }

  if (isBrowser && typeof window.fbq === "function") {
    window.fbq("track", "PageView");
  }
};
