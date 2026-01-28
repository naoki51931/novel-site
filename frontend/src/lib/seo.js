export const isGoogleCrawler = () => {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  return /Googlebot|Google-InspectionTool|AdsBot-Google|Google-Other/i.test(ua);
};
