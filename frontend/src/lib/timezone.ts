export const USER_TIMEZONE_STORAGE_KEY = "user_timezone";
export const DEFAULT_USER_TIMEZONE = "Asia/Tokyo";

export type TimeZoneOption = { value: string; labelJa: string; labelEn: string };

export const TIME_ZONE_OPTIONS: TimeZoneOption[] = [
  { value: "Asia/Tokyo", labelJa: "日本時間 (JST)", labelEn: "Japan Time (JST)" },
  { value: "UTC", labelJa: "協定世界時 (UTC)", labelEn: "Coordinated Universal Time (UTC)" },
  { value: "America/Los_Angeles", labelJa: "米国太平洋時間", labelEn: "US Pacific Time" },
  { value: "America/Denver", labelJa: "米国山岳部時間", labelEn: "US Mountain Time" },
  { value: "America/Chicago", labelJa: "米国中部時間", labelEn: "US Central Time" },
  { value: "America/New_York", labelJa: "米国東部時間", labelEn: "US Eastern Time" },
  { value: "America/Toronto", labelJa: "トロント", labelEn: "Toronto" },
  { value: "America/Sao_Paulo", labelJa: "サンパウロ", labelEn: "Sao Paulo" },
  { value: "Europe/London", labelJa: "ロンドン", labelEn: "London" },
  { value: "Europe/Paris", labelJa: "パリ", labelEn: "Paris" },
  { value: "Europe/Berlin", labelJa: "ベルリン", labelEn: "Berlin" },
  { value: "Europe/Madrid", labelJa: "マドリード", labelEn: "Madrid" },
  { value: "Europe/Rome", labelJa: "ローマ", labelEn: "Rome" },
  { value: "Asia/Seoul", labelJa: "韓国時間", labelEn: "Korea Time" },
  { value: "Asia/Shanghai", labelJa: "中国標準時", labelEn: "China Standard Time" },
  { value: "Asia/Taipei", labelJa: "台湾時間", labelEn: "Taipei Time" },
  { value: "Asia/Hong_Kong", labelJa: "香港時間", labelEn: "Hong Kong Time" },
  { value: "Asia/Singapore", labelJa: "シンガポール時間", labelEn: "Singapore Time" },
  { value: "Asia/Bangkok", labelJa: "バンコク", labelEn: "Bangkok" },
  { value: "Asia/Jakarta", labelJa: "ジャカルタ", labelEn: "Jakarta" },
  { value: "Asia/Kolkata", labelJa: "インド標準時", labelEn: "India Standard Time" },
  { value: "Australia/Sydney", labelJa: "シドニー", labelEn: "Sydney" },
  { value: "Pacific/Auckland", labelJa: "オークランド", labelEn: "Auckland" },
];

export function isValidTimeZone(value: string | null | undefined): value is string {
  const tz = String(value || "").trim();
  if (!tz) return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz }).format(new Date());
    return true;
  } catch {
    return false;
  }
}

export function normalizeTimeZone(value: string | null | undefined): string {
  const tz = String(value || "").trim();
  return isValidTimeZone(tz) ? tz : DEFAULT_USER_TIMEZONE;
}

export function getUserTimeZone(): string {
  if (typeof window === "undefined") return DEFAULT_USER_TIMEZONE;
  try {
    return normalizeTimeZone(window.localStorage.getItem(USER_TIMEZONE_STORAGE_KEY));
  } catch {
    return DEFAULT_USER_TIMEZONE;
  }
}

export function setUserTimeZone(value: string | null | undefined): string {
  const tz = normalizeTimeZone(value);
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(USER_TIMEZONE_STORAGE_KEY, tz);
      window.dispatchEvent(new CustomEvent("user-timezone-change", { detail: { timeZone: tz } }));
    } catch {
      // ignore storage errors
    }
  }
  return tz;
}

export function timeZoneLabel(value: string | null | undefined): string {
  const tz = normalizeTimeZone(value);
  if (tz === "Asia/Tokyo") return "JST";
  if (tz === "UTC") return "UTC";
  return tz;
}

export function formatDateTimeInUserTimeZone(
  value: string | number | Date | null | undefined,
  locale: string = "ja-JP",
  options: Intl.DateTimeFormatOptions = {},
): string {
  if (value === null || value === undefined || value === "") return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const timeZone = getUserTimeZone();
  const formatted = date.toLocaleString(locale, { timeZone, ...options });
  return formatted ? `${formatted} ${timeZoneLabel(timeZone)}` : "";
}
