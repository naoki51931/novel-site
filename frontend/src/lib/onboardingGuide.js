const GUIDE_AD_TRAFFIC_SESSION_KEY = "onboarding_ads_traffic_v1";
const GUIDE_DISMISSED_BUBBLES_KEY = "onboarding_dismissed_bubbles_v1";

export const markGoogleAdsTraffic = (search = "") => {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(search || "");
  const utmSource = (params.get("utm_source") || "").toLowerCase();
  const hasAdParams =
    params.has("gclid") ||
    params.has("gbraid") ||
    params.has("wbraid") ||
    utmSource === "google" ||
    utmSource === "googleads";
  const referrer = (document.referrer || "").toLowerCase();
  const hasAdReferrer =
    referrer.includes("googleadservices.com") ||
    referrer.includes("google.com/aclk") ||
    referrer.includes("ads.google.com");
  if (!hasAdParams && !hasAdReferrer) return false;
  try {
    sessionStorage.setItem(GUIDE_AD_TRAFFIC_SESSION_KEY, "1");
  } catch {
    // ignore
  }
  return true;
};

export const isOnboardingGuideEligible = () => {
  if (typeof window === "undefined") return false;
  const username = (localStorage.getItem("username") || "").toLowerCase();
  const hasDemoUser = username === "demo02";
  const hasDemoCookie = (document.cookie || "").toLowerCase().includes("demo02");
  const hasAdsSession = sessionStorage.getItem(GUIDE_AD_TRAFFIC_SESSION_KEY) === "1";
  return hasDemoUser || hasDemoCookie || hasAdsSession;
};

export const getDismissedGuideBubbles = () => {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(GUIDE_DISMISSED_BUBBLES_KEY);
    const parsed = JSON.parse(raw || "[]");
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.map((v) => String(v)));
  } catch {
    return new Set();
  }
};

export const dismissGuideBubble = (key) => {
  if (typeof window === "undefined" || !key) return;
  const next = getDismissedGuideBubbles();
  next.add(String(key));
  try {
    localStorage.setItem(GUIDE_DISMISSED_BUBBLES_KEY, JSON.stringify(Array.from(next)));
  } catch {
    // ignore
  }
};
