const APP_UA_MARKER = "NovelSiteAndroidApp";

function isAndroid() {
  if (typeof navigator === "undefined") return false;
  return /Android/i.test(navigator.userAgent || "");
}

function isInsideAndroidApp() {
  if (typeof navigator === "undefined") return false;
  return (navigator.userAgent || "").includes(APP_UA_MARKER);
}

export function shouldRedirectToAndroidApp() {
  // Android標準ブラウザからのみ app deep link へ戻す。
  // アプリ内WebViewでは deep link にせず、そのままWeb遷移で完了させる。
  return isAndroid() && !isInsideAndroidApp();
}

export function buildAndroidAppLoginUrl({ token, username, redirect = "/mypage" }) {
  const params = new URLSearchParams();
  params.set("token", token || "");
  if (username) params.set("username", username);
  if (redirect && redirect.startsWith("/")) params.set("redirect", redirect);
  return `novelsite://oauth/callback?${params.toString()}`;
}

export function redirectToAndroidAppLogin(payload) {
  // Only redirect back to the native app when the current flow explicitly opts-in.
  // Otherwise Android web users who happen to have the app installed get kicked out of the web site.
  if (!payload?.appClient) return false;
  if (!shouldRedirectToAndroidApp()) return false;
  const url = buildAndroidAppLoginUrl(payload || {});
  window.location.href = url;
  return true;
}
