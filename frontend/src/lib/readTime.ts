export function formatReadMinutes(
  minutes: number | null | undefined,
  t: (messages: Record<string, string>, vars?: Record<string, string | number>) => string
) {
  const value = Number(minutes || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "";
  }
  return t({ ja: "読了{{minutes}}分", en: "{{minutes}} min read" }, { minutes: value });
}
